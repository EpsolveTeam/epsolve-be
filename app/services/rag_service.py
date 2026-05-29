import asyncio
import re
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from loguru import logger

from app.models.knowledge import KnowledgeBase
from app.core.config import settings
from app.services.embedding_service import get_embedding


try:
    import google.genai as genai
    from google.genai.types import Part
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

import httpx

# ── BM25 Engine ──────────────────────────────────────────────────────────────
try:
    from rank_bm25 import BM25Okapi
    RANK_BM25_AVAILABLE = True
except ImportError:
    RANK_BM25_AVAILABLE = False
    logger.warning("rank_bm25 not installed; BM25 fallback will be skipped")

import numpy as np


class BM25Engine:
    """
    BM25 retrieval engine built from KnowledgeBase.content.
    Supports per-category caching and lazy rebuild.
    """

    def __init__(self):
        self._corpus_by_category: Dict[str, List[str]] = {}
        self._bm25_by_category: Dict[str, BM25Okapi] = {}
        self._doc_ids_by_category: Dict[str, List[int]] = {}
        self._doc_faq_ids_by_category: Dict[str, List[Optional[str]]] = {}
        self._global_dirty = True

    def _tokenize(self, text: str) -> List[str]:
        """Simple whitespace + lower-case tokenizer."""
        return re.findall(r"\w+", text.lower())

    def rebuild(self, db: Session):
        """ (Re)build BM25 indexes for all categories. """
        all_docs = db.query(KnowledgeBase).all()
        by_cat: Dict[str, List[KnowledgeBase]] = {}
        for doc in all_docs:
            cat = doc.category or "General"
            by_cat.setdefault(cat, []).append(doc)

        self._corpus_by_category.clear()
        self._bm25_by_category.clear()
        self._doc_ids_by_category.clear()
        self._doc_faq_ids_by_category.clear()

        for cat, docs in by_cat.items():
            tokenized = [self._tokenize(d.content) for d in docs]
            self._corpus_by_category[cat] = [d.content for d in docs]
            self._bm25_by_category[cat] = BM25Okapi(tokenized)
            self._doc_ids_by_category[cat] = [d.id for d in docs]
            self._doc_faq_ids_by_category[cat] = [d.faq_id for d in docs]

        self._global_dirty = False
        logger.info(f"BM25 index rebuilt for {len(by_cat)} categories ({sum(len(v) for v in by_cat.values())} docs)")

    def _ensure_index(self, db: Session):
        if self._global_dirty or not self._bm25_by_category:
            self.rebuild(db)

    def search(
        self,
        query_text: str,
        db: Session,
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[KnowledgeBase]:
        """Return BM25 top-k KnowledgeBase documents."""
        self._ensure_index(db)
        tokenized_query = self._tokenize(query_text)

        candidates: List[Tuple[float, int]] = []  # (score, doc_id)

        categories = [category] if category else list(self._bm25_by_category.keys())

        for cat in categories:
            bm25 = self._bm25_by_category.get(cat)
            if bm25 is None:
                continue
            scores = bm25.get_scores(tokenized_query)
            doc_ids = self._doc_ids_by_category[cat]
            for idx, score in enumerate(scores):
                if score > 0:
                    candidates.append((score, doc_ids[idx]))

        # Sort by BM25 score descending
        candidates.sort(key=lambda x: x[0], reverse=True)
        top_ids = [doc_id for _, doc_id in candidates[:limit]]

        if not top_ids:
            return []

        # Preserve order from scores
        docs = db.query(KnowledgeBase).filter(KnowledgeBase.id.in_(top_ids)).all()
        id_map = {d.id: d for d in docs}
        return [id_map[i] for i in top_ids if i in id_map]


# ── Singleton BM25 engine ────────────────────────────────────────────────────
_bm25_engine: Optional[BM25Engine] = None


def get_bm25_engine() -> BM25Engine:
    global _bm25_engine
    if _bm25_engine is None:
        _bm25_engine = BM25Engine()
    return _bm25_engine


def invalidate_bm25_cache():
    """Call after create/update/delete on KnowledgeBase to force BM25 rebuild."""
    global _bm25_engine
    if _bm25_engine is not None:
        _bm25_engine._global_dirty = True
        logger.info("BM25 cache invalidated")


# ── Reciprocal Rank Fusion ───────────────────────────────────────────────────
RECIPROCAL_K = 60  # standard constant for RRF


def reciprocal_rank_fusion(
    vector_docs: List[KnowledgeBase],
    bm25_docs: List[KnowledgeBase],
    final_limit: int = 5
) -> List[KnowledgeBase]:
    """
    Reciprocal Rank Fusion merging two ranked lists.
    RRF score = sum(1 / (k + rank(entry_in_list))).
    """
    scores: Dict[int, float] = {}

    for rank, doc in enumerate(vector_docs, start=1):
        scores[doc.id] = scores.get(doc.id, 0.0) + 1.0 / (RECIPROCAL_K + rank)

    for rank, doc in enumerate(bm25_docs, start=1):
        scores[doc.id] = scores.get(doc.id, 0.0) + 1.0 / (RECIPROCAL_K + rank)

    # Sort by fusion score descending
    ranked_ids = [doc_id for doc_id, _ in sorted(scores.items(), key=lambda x: x[1], reverse=True)]

    if not ranked_ids:
        return []

    # Build doc lookup from both lists (avoid extra DB query)
    seen: Dict[int, KnowledgeBase] = {}
    for d in vector_docs:
        seen[d.id] = d
    for d in bm25_docs:
        seen.setdefault(d.id, d)

    fused = [seen[did] for did in ranked_ids if did in seen]
    return fused[:final_limit]


# ── Ticket-Flag constants ────────────────────────────────────────────────────
TICKET_FLAG = "CREATE_SUPPORT_TICKET_FLAG"

TICKET_SYSTEM_PROMPT = (
    "You are a helpful assistant for Epson printer support. "
    "Answer using ONLY the provided context. "
    "If the answer is NOT found in the provided context, you MUST respond with exactly: "
    f"'{TICKET_FLAG}' "
    "without any additional text. "
    "Do NOT make up information. Be concise."
)


# ── RAG Service ──────────────────────────────────────────────────────────────
class RAGService:
    def __init__(
        self,
        db: Session,
        use_llm: bool = True
    ):
        self.db = db
        self.use_llm = use_llm
        self.bm25 = get_bm25_engine()

        if use_llm:
            if not GENAI_AVAILABLE:
                raise ImportError("google-genai package required for LLM.")
            if not settings.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY not configured")
            self.genai_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            self.chat_model = "gemini-2.5-flash-lite"
            logger.success("Gemini 2.5 Flash Lite initialized")
        else:
            self.genai_client = None
            self.chat_model = None
            logger.info("RAGService: LLM disabled")

    async def search_similar_docs(
        self,
        query_embedding: List[float],
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[KnowledgeBase]:
        query = self.db.query(KnowledgeBase).filter(
            KnowledgeBase.embedding.is_not(None)
        )
        if category:
            query = query.filter(KnowledgeBase.category == category)
        results = query.order_by(
            KnowledgeBase.embedding.cosine_distance(query_embedding)
        ).limit(limit).all()
        return results

    async def search_hybrid_docs(
        self,
        query_embedding: List[float],
        query_text: str,
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[KnowledgeBase]:
        """
        Hybrid retrieval: combine vector (pgvector) + BM25 via Reciprocal Rank Fusion.
        """
        # 1. Vector retrieval (pgvector cosine distance)
        logger.info("Hybrid: fetching vector results")
        vector_docs = await self.search_similar_docs(
            query_embedding=query_embedding,
            limit=limit * 2,  # fetch more for fusion
            category=category
        )
        logger.info(f"Hybrid: vector returned {len(vector_docs)} docs")

        # 2. BM25 retrieval
        bm25_docs = []
        if RANK_BM25_AVAILABLE:
            try:
                bm25_docs = self.bm25.search(
                    query_text=query_text,
                    db=self.db,
                    limit=limit * 2,
                    category=category
                )
                logger.info(f"Hybrid: BM25 returned {len(bm25_docs)} docs")
            except Exception as e:
                logger.error(f"BM25 search failed: {e}")
        else:
            logger.warning("BM25 not available, using vector-only")

        # 3. Reciprocal Rank Fusion
        fused = reciprocal_rank_fusion(vector_docs, bm25_docs, final_limit=limit)
        logger.info(f"Hybrid: fused result count = {len(fused)}")
        return fused

    def format_context(self, docs: List[KnowledgeBase]) -> str:
        context_parts = []
        for i, doc in enumerate(docs, 1):
            source_info = f"[Source {i}: {doc.title}]"
            if doc.category:
                source_info += f" (Category: {doc.category})"
            if doc.source_url:
                source_info += f"\nURL: {doc.source_url}"
            context_parts.append(f"{source_info}\n{doc.content}")
        return "\n\n---\n\n".join(context_parts)

    async def generate_response(
        self,
        query: str,
        context: str,
        system_prompt: Optional[str] = None
    ) -> str:
        if not self.use_llm or self.genai_client is None:
            raise RuntimeError("LLM disabled")
        if system_prompt is None:
            system_prompt = TICKET_SYSTEM_PROMPT
        user_message = f"Context:\n{context}\n\nQuestion: {query}"
        try:
            response = await self.genai_client.aio.models.generate_content(
                model=self.chat_model,
                contents=user_message,
                config={"system_instruction": system_prompt}
            )
            return response.text
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise

    def _is_ticket_flag_response(self, answer: str) -> bool:
        """Check if the answer indicates 'no answer in context'."""
        cleaned = answer.strip().upper().replace(".", "").replace("!", "").strip()
        if cleaned == TICKET_FLAG:
            return True
        # Also catch variations like "CREATE_SUPPORT_TICKET_FLAG."
        if TICKET_FLAG in answer.upper():
            return True
        # Fallback: check for "not found" / "tidak menemukan" patterns
        fallback_phrases = [
            "tidak menemukan", "not in context", "tidak ada jawaban",
            "tidak ditemukan", "no information", "i couldn't find",
            "cannot find", "not available"
        ]
        lower = answer.lower()
        for phrase in fallback_phrases:
            if phrase in lower:
                return True
        return False

    async def query(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main RAG query: hybrid retrieve docs and generate answer.
        If answer is not found in context, returns CREATE_SUPPORT_TICKET_FLAG.
        Supports optional image_url for multimodal queries.
        """
        logger.info(f"RAG query: '{query[:50]}...' | limit={limit} | image={'yes' if image_url else 'no'}")

        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(None, get_embedding, query)

        # Use hybrid retrieval (vector + BM25 + RRF)
        docs = await self.search_hybrid_docs(
            query_embedding=query_embedding,
            query_text=query,
            limit=limit,
            category=category
        )

        if not docs:
            return {
                "answer": TICKET_FLAG,
                "sources": [],
                "query": query,
                "no_answer": True
            }

        context = self.format_context(docs)

        if self.use_llm:
            try:
                if image_url:
                    # Download image
                    async with httpx.AsyncClient(timeout=30) as client:
                        resp = await client.get(image_url)
                        resp.raise_for_status()
                        image_bytes = resp.content
                    mime = resp.headers.get("content-type", "image/jpeg")
                    if not mime.startswith("image/"):
                        mime = "image/jpeg"
                    image_part = Part.from_bytes(data=image_bytes, mime_type=mime)
                    contents = [
                        image_part,
                        f"Context:\n{context}\n\nQuestion: {query}"
                    ]
                    response = await self.genai_client.aio.models.generate_content(
                        model=self.chat_model,
                        contents=contents,
                        config={
                            "system_instruction": (
                                "You are a helpful Epson support assistant. "
                                "Use both the image and provided context to answer. "
                                f"If uncertain, respond exactly: '{TICKET_FLAG}'"
                            )
                        }
                    )
                    answer = response.text
                else:
                    answer = await self.generate_response(query, context, system_prompt=TICKET_SYSTEM_PROMPT)
            except Exception as e:
                logger.error(f"Generation failed (image fallback): {e}")
                answer = await self.generate_response(query, context, system_prompt=TICKET_SYSTEM_PROMPT)
        else:
            answer = "LLM not enabled."

        # Post-check: if response is ticket-flag, override
        if self._is_ticket_flag_response(answer):
            answer = TICKET_FLAG

        sources = []
        for doc in docs:
            similarity = max(0.0, 0.99 - (len(sources) * 0.01))
            sources.append({
                "id": doc.id,
                "faq_id": doc.faq_id,
                "title": doc.title,
                "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                "category": doc.category,
                "source_url": getattr(doc, "source_url", None),
                "similarity": similarity
            })

        logger.success(f"RAG query completed with {len(docs)} sources | ticket_flag={answer == TICKET_FLAG}")
        return {
            "answer": answer,
            "sources": sources,
            "query": query,
            "no_answer": answer == TICKET_FLAG
        }
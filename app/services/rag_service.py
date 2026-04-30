import asyncio
from typing import List, Optional, Dict, Any
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


class RAGService:
    def __init__(
        self,
        db: Session,
        use_llm: bool = True
    ):
        self.db = db
        self.use_llm = use_llm

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

    def format_context(self, docs: List[KnowledgeBase]) -> str:
        context_parts = []
        for i, doc in enumerate(docs, 1):
            source_info = f"[Source {i}: {doc.title}]"
            if doc.category:
                source_info += f" (Category: {doc.category})"
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
            system_prompt = (
                "You are a helpful assistant for Epson printer support. "
                "Answer using ONLY the provided context. "
                "If answer not in context, say so. Do not make up info. Be concise."
            )
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

    async def query(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None,
        image_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main RAG query: retrieve docs and generate answer.
        Supports optional image_url for multimodal queries.
        """
        logger.info(f"RAG query: '{query[:50]}...' | limit={limit} | image={'yes' if image_url else 'no'}")

        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(None, get_embedding, query)

        docs = await self.search_similar_docs(
            query_embedding=query_embedding,
            limit=limit,
            category=category
        )

        if not docs:
            return {
                "answer": "I couldn't find relevant information. Please rephrase or contact support.",
                "sources": [],
                "query": query
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
                    # Determine mime type
                    mime = resp.headers.get("content-type", "image/jpeg")
                    if not mime.startswith("image/"):
                        mime = "image/jpeg"
                    # Build multimodal contents: image + text (context+query)
                    image_part = Part.from_bytes(data=image_bytes, mime_type=mime)
                    contents = [
                        image_part,
                        f"Context:\n{context}\n\nQuestion: {query}"
                    ]
                    response = await self.genai_client.aio.models.generate_content(
                        model=self.chat_model,
                        contents=contents,
                        config={"system_instruction": "You are a helpful Epson support assistant. Use both the image and provided context to answer. If uncertain, say so."}
                    )
                    answer = response.text
                else:
                    answer = await self.generate_response(query, context)
            except Exception as e:
                logger.error(f"Generation failed (image fallback): {e}")
                answer = await self.generate_response(query, context)
        else:
            answer = "LLM not enabled."

        sources = []
        for doc in docs:
            similarity = max(0.0, 0.99 - (len(sources) * 0.01))
            sources.append({
                "id": doc.id,
                "title": doc.title,
                "content": doc.content[:200] + "..." if len(doc.content) > 200 else doc.content,
                "category": doc.category,
                "source_url": getattr(doc, "source_url", None),
                "similarity": similarity
            })

        logger.success(f"RAG query completed with {len(docs)} sources")
        return {"answer": answer, "sources": sources, "query": query}

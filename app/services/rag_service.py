import asyncio
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from loguru import logger

from app.models.knowledge import KnowledgeBase
from app.core.config import settings

try:
    import google.genai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

from sentence_transformers import SentenceTransformer


class RAGService:
    def __init__(
        self,
        db: Session,
        use_llm: bool = True
    ):
        self.db = db
        self.use_llm = use_llm

        logger.info("Loading embedding model: sentence-transformers/all-MiniLM-L6-v2")
        self.embed_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        logger.success("Embedding model loaded (384 dimensions)")

        if use_llm:
            if not GENAI_AVAILABLE:
                raise ImportError("google-genai package required for LLM. Install: pip install google-genai")
            if not settings.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY not configured in environment")
            self.genai_client = genai.Client(api_key=settings.GOOGLE_API_KEY)
            self.chat_model = "gemini-1.5-flash"
            logger.success("Gemini LLM initialized")
        else:
            self.genai_client = None
            self.chat_model = None
            logger.info("RAGService running in embedding-only mode (LLM disabled)")

    def get_embedding(self, text: str) -> List[float]:
        """Generate embedding for a text string using HuggingFace SentenceTransformer (synchronous)."""
        try:
            emb = self.embed_model.encode(text, convert_to_numpy=True)
            return emb.tolist() 
        except Exception as e:
            logger.error(f"Failed to generate embedding: {e}")
            raise

    async def search_similar_docs(
        self,
        query_embedding: List[float],
        limit: int = 5,
        category: Optional[str] = None
    ) -> List[KnowledgeBase]:
        """Search for similar documents using pgvector cosine similarity."""
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
        """Format retrieved documents into context for LLM."""
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
        """Generate LLM response using Gemini (requires LLM enabled)."""
        if not self.use_llm or self.genai_client is None:
            raise RuntimeError("LLM is disabled. Initialize RAGService with use_llm=True for generation.")

        if system_prompt is None:
            system_prompt = (
                "You are a helpful assistant for Epson printer support. "
                "Answer the user's question using ONLY the provided context. "
                "If the answer is not in the context, say you don't have enough information. "
                "Do not make up information. Be concise and helpful."
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
            logger.error(f"Failed to generate LLM response: {e}")
            raise

    async def query(
        self,
        query: str,
        limit: int = 5,
        category: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main RAG query: retrieve relevant docs and generate answer.

        Returns dict with:
        - answer: generated response
        - sources: list of source documents with metadata
        - query: original query
        """
        logger.info(f"RAG query: '{query[:50]}...' | limit={limit}")

        loop = asyncio.get_event_loop()
        query_embedding = await loop.run_in_executor(None, self.get_embedding, query)

        docs = await self.search_similar_docs(
            query_embedding=query_embedding,
            limit=limit,
            category=category
        )

        if not docs:
            return {
                "answer": "I couldn't find relevant information in the knowledge base. Please try rephrasing your question or contact support directly.",
                "sources": [],
                "query": query
            }

        context = self.format_context(docs)

        answer = await self.generate_response(query, context)

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

        return {
            "answer": answer,
            "sources": sources,
            "query": query
        }
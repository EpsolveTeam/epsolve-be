"""
Service untuk generate embeddings dari teks menggunakan SentenceTransformer.
Model dimuat sekali (singleton) dan di-reuse across requests.
"""

from sentence_transformers import SentenceTransformer
from loguru import logger
from typing import List

_model: SentenceTransformer | None = None

def get_embedding_model() -> SentenceTransformer:
    """Get or load the SentenceTransformer model (singleton)."""
    global _model
    if _model is None:
        logger.info("Loading SentenceTransformer model: sentence-transformers/all-MiniLM-L6-v2")
        _model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
        logger.success("Embedding model loaded (384 dimensions)")
    return _model

def get_embedding(text: str) -> List[float]:
    """Generate embedding for a text string."""
    model = get_embedding_model()
    emb = model.encode(text, convert_to_numpy=True)
    return emb.tolist()

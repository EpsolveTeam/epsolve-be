"""
Script to seed the KnowledgeBase with Epson FAQ data.
Run: python scripts/seed_faq.py
Requires: GOOGLE_API_KEY set in environment (for LLM, not used in seeding)
"""

import json
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
from loguru import logger

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, create_engine
from app.core.config import settings
from app.models.knowledge import KnowledgeBase
from app.services.rag_service import RAGService

# Constants
FAQ_JSON_PATH = project_root / "epson_allinoneprinter_faq_clean.json"
BATCH_SIZE = 100  # Process in batches to manage memory


def load_faq_data(json_path: Path) -> List[Dict[str, Any]]:
    """Load and validate FAQ chunks from JSON."""
    logger.info(f"Loading FAQ data from {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = data.get("chunks", [])
    logger.info(f"Loaded {len(chunks)} FAQ chunks")
    return chunks


def create_knowledge_entry(chunk: Dict[str, Any]) -> KnowledgeBase:
    """Create KnowledgeBase entry from a FAQ chunk."""
    metadata = chunk.get("metadata", {})
    chunk_type = metadata.get("chunk_type", "faq")
    product_name = metadata.get("product_name", "Epson Printer")
    question = metadata.get("question", "")
    faq_id = metadata.get("faq_id", chunk.get("id", ""))

    # Build title based on chunk type
    if chunk_type == "faq_overview":
        title = f"Epson {product_name} - Overview ({chunk.get('id', '')})"
    else:
        # Truncate question for title
        title = f"Q: {question[:100]}..." if len(question) > 100 else f"Q: {question}"

    # Build content (already clean)
    content = chunk.get("content", "")

    # Category based on series or default
    series = metadata.get("series", "All-In-Ones")
    category = f"Epson {series}"

    # Source URL
    source_url = chunk.get("source_url", "")

    return KnowledgeBase(
        title=title,
        content=content,
        category=category,
        source_url=source_url,
        division="Support"
    )


def seed_database(
    engine,
    chunks: List[Dict[str, Any]],
    batch_size: int = BATCH_SIZE
) -> None:
    """Seed database with FAQ data, generating embeddings synchronously."""
    # Initialize RAGService in embedding-only mode (no Gemini/L LLM needed)
    rag_service = RAGService(db=None, use_llm=False)

    total_chunks = len(chunks)
    logger.info(f"Starting seeding of {total_chunks} chunks in batches of {batch_size}")

    with Session(engine) as session:
        batches = [chunks[i:i + batch_size] for i in range(0, total_chunks, batch_size)]

        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} chunks)")

            # Create KnowledgeBase objects without embeddings first
            kb_entries = [create_knowledge_entry(chunk) for chunk in batch]

            # Generate embeddings synchronously (SentenceTransformer is CPU-bound)
            texts = [entry.content for entry in kb_entries]
            logger.info(f"Generating embeddings for {len(texts)} texts...")

            try:
                embeddings = []
                for text in texts:
                    emb = rag_service.get_embedding(text)  # sync call
                    embeddings.append(emb)

                # Assign embeddings to entries
                for entry, emb in zip(kb_entries, embeddings):
                    entry.embedding = emb

                # Bulk insert
                session.add_all(kb_entries)
                session.commit()

                logger.success(f"Batch {batch_idx + 1} committed ({len(kb_entries)} records)")

            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} failed: {e}")
                session.rollback()
                raise

    logger.success("Seeding complete! KnowledgeBase now contains embeddings from all-MiniLM-L6-v2.")


def main():
    """Main entry point."""
    logger.info("Initializing FAQ data seeding...")

    # Load FAQ data
    if not FAQ_JSON_PATH.exists():
        logger.error(f"FAQ JSON not found at {FAQ_JSON_PATH}")
        sys.exit(1)

    chunks = load_faq_data(FAQ_JSON_PATH)

    # Create database engine
    database_url = settings.DATABASE_URL
    engine = create_engine(database_url)

    # Check if already seeded
    with Session(engine) as session:
        existing_count = session.query(KnowledgeBase).count()
        expected_count = len(chunks)
        if existing_count >= expected_count:
            logger.info(f"KnowledgeBase already seeded ({existing_count}/{expected_count} entries). Skipping.")
            return
        else:
            logger.info(f"KnowledgeBase has {existing_count} entries, need {expected_count}. Proceeding with seeding...")

    # Run seeding (synchronous)
    try:
        seed_database(engine, chunks)
    except KeyboardInterrupt:
        logger.warning("Seeding interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Seeding failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

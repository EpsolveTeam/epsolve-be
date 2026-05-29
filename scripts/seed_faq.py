"""
Script to seed the KnowledgeBase with Epson FAQ data.
Run: python scripts/seed_faq.py
     python scripts/seed_faq.py --json epson_printer_faq_clean.json
"""

import json
import sys
import os
import argparse
from pathlib import Path
from typing import List, Dict, Any
import re
from loguru import logger

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session, create_engine
from app.core.config import settings
from app.models.knowledge import KnowledgeBase
from app.services.embedding_service import get_embedding

DEFAULT_JSON = "epson_allinoneprinter_faq_clean.json"
BATCH_SIZE = 100


def load_faq_data(json_path: Path) -> List[Dict[str, Any]]:
    """Load and validate FAQ chunks from JSON.
    Supports both formats:
      - { "chunks": [...] }  (old format from epson_allinoneprinter_faq_clean.json)
      - { "data": [...] }    (new format from epson_printer_faq_clean.json)
    """
    logger.info(f"Loading FAQ data from {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    chunks = data.get("chunks") or data.get("data", [])
    logger.info(f"Loaded {len(chunks)} FAQ chunks")
    return chunks


def create_knowledge_entry(chunk: Dict[str, Any]) -> KnowledgeBase:
    """Create KnowledgeBase entry from a FAQ chunk.
    Supports both old format (chunk has top-level id/source_url, metadata has series)
    and new format (chunk has metadata.source_url, metadata has category instead of series).
    """
    metadata = chunk.get("metadata", {})
    chunk_type = metadata.get("chunk_type", "faq")
    product_name = metadata.get("product_name", "Epson Printer")
    question = metadata.get("question", "")
    faq_id = metadata.get("faq_id", chunk.get("id", ""))

    chunk_id = chunk.get("id", "")
    if chunk_type == "faq_overview":
        title = (question or "").strip()
        if not title:
            title = f"Epson {product_name} - Overview ({chunk_id})" if chunk_id else f"Epson {product_name} - Overview"
    else:
        title = (question or "").strip()

    raw_content = chunk.get("content", "")
    content = raw_content
    if "Answer Context:" in raw_content:
        content = raw_content.split("Answer Context:", 1)[1].lstrip()
    else:
        m = re.search(r"\nA:\s*", raw_content)
        if m:
            content = raw_content[m.end():].lstrip()
    content = re.sub(r"^(Answer\s*:?\s*)", "", content, flags=re.IGNORECASE).strip()

    # Category: use metadata.category if available (new format), else build from series (old format)
    metadata_category = metadata.get("category", "")
    if metadata_category:
        category = metadata_category
    else:
        series = metadata.get("series", "All-In-Ones")
        category = f"Epson {series}"

    # Source URL: check chunk top-level first (old format), then fallback to metadata (new format)
    source_url = chunk.get("source_url", "") or metadata.get("source_url", "")

    return KnowledgeBase(
        title=title,
        content=content,
        category=category,
        source_url=source_url,
        division="Support",
        faq_id=faq_id if faq_id else None
    )


def seed_database(
    engine,
    chunks: List[Dict[str, Any]],
    batch_size: int = BATCH_SIZE,
    on_duplicate: str = "skip",
) -> None:
    """Seed database with FAQ data, generating embeddings synchronously."""
    total_chunks = len(chunks)
    logger.info(f"Starting seeding of {total_chunks} chunks in batches of {batch_size}")

    with Session(engine) as session:
        batches = [chunks[i:i + batch_size] for i in range(0, total_chunks, batch_size)]
        # Prevent Query-invoked autoflush causing unique constraint errors inside the batch loop.
        # We can safely disable autoflush because we always call session.commit() per batch.
        session.autoflush = False


        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)} ({len(batch)} chunks)")

            # Create KnowledgeBase objects without embeddings first
            kb_entries = [create_knowledge_entry(chunk) for chunk in batch]

            # Generate embeddings synchronously using embedding service
            texts = [entry.content for entry in kb_entries]
            logger.info(f"Generating embeddings for {len(texts)} texts...")

            try:
                # Generate embeddings one by one (model is cached)
                embeddings = []
                for text in texts:
                    emb = get_embedding(text)
                    embeddings.append(emb)

                # Assign embeddings to entries
                for entry, emb in zip(kb_entries, embeddings):
                    entry.embedding = emb

                # Bulk insert with duplicate handling
                for entry in kb_entries:
                    if entry.faq_id:
                        existing = session.query(KnowledgeBase).filter(KnowledgeBase.faq_id == entry.faq_id).first()
                    else:
                        existing = None

                    if existing is not None:
                        if on_duplicate == "upsert":
                            existing.title = entry.title
                            existing.content = entry.content
                            existing.category = entry.category
                            existing.division = entry.division
                            existing.source_url = entry.source_url
                            existing.embedding = entry.embedding
                        # else: skip
                    else:
                        session.add(entry)

                session.commit()

                logger.success(f"Batch {batch_idx + 1} committed ({len(kb_entries)} records)")

            except Exception as e:
                logger.error(f"Batch {batch_idx + 1} failed: {e}")
                session.rollback()
                raise

    logger.success("Seeding complete! KnowledgeBase now contains embeddings from all-MiniLM-L6-v2.")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Seed FAQ data into KnowledgeBase")
    parser.add_argument(
        "--json",
        type=str,
        default=DEFAULT_JSON,
        help=f"JSON filename to seed (default: {DEFAULT_JSON})"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force seeding even if KnowledgeBase already has entries"
    )
    parser.add_argument(
        "--on-duplicate",
        choices=["skip", "upsert"],
        default="skip",
        help="How to handle duplicate faq_id when inserting into KnowledgeBase. 'skip' ignores existing rows, 'upsert' updates existing rows. Default: skip"
    )
    args = parser.parse_args()

    logger.info("Initializing FAQ data seeding...")

    # Determine JSON path based on argument
    faq_json_path = project_root / args.json
    logger.info(f"Using FAQ JSON: {faq_json_path}")

    # Load FAQ data
    if not faq_json_path.exists():
        logger.error(f"FAQ JSON not found at {faq_json_path}")
        sys.exit(1)

    chunks = load_faq_data(faq_json_path)

    # Create database engine
    database_url = settings.DATABASE_URL
    engine = create_engine(database_url)

    # Check if already seeded (skip check when --force is used)
    with Session(engine) as session:
        existing_count = session.query(KnowledgeBase).count()
        expected_count = len(chunks)
        if not args.force and existing_count >= expected_count:
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

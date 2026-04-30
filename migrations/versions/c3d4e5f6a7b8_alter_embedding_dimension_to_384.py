"""alter_embedding_dimension_to_384

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-30 13:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: change embedding from Vector(1536) to Vector(384)."""
    # Drop existing index (if exists)
    op.drop_index('ix_knowledgebase_embedding_cosine', table_name='knowledgebase', if_exists=True)

    # Drop old embedding column and add new one with dimension 384 using pgvector type
    # WARNING: existing embeddings will be lost — re-seed required
    op.execute('ALTER TABLE knowledgebase DROP COLUMN IF EXISTS embedding')
    op.execute('ALTER TABLE knowledgebase ADD COLUMN embedding vector(384)')

    # Recreate HNSW index for cosine similarity
    op.create_index(
        'ix_knowledgebase_embedding_cosine',
        'knowledgebase',
        ['embedding'],
        postgresql_using='hnsw',
        postgresql_ops={'embedding': 'vector_cosine_ops'}
    )


def downgrade() -> None:
    """Downgrade schema: revert to Vector(1536)."""
    op.drop_index('ix_knowledgebase_embedding_cosine', table_name='knowledgebase', if_exists=True)
    op.execute('ALTER TABLE knowledgebase DROP COLUMN embedding')
    op.execute('ALTER TABLE knowledgebase ADD COLUMN embedding vector(1536)')
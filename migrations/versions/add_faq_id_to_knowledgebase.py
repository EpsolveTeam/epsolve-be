"""Add faq_id column to knowledge_base

Revision ID: add_faq_id_to_knowledgebase
Revises: ead8f9f62b0c
Create Date: 2026-05-28 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision = 'add_faq_id_to_knowledgebase'
down_revision = 'ead8f9f62b0c'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add faq_id column to knowledgebase table."""
    op.add_column(
        'knowledgebase',
        sa.Column('faq_id', sa.String(100), nullable=True, unique=True)
    )
    op.create_index(op.f('ix_knowledgebase_faq_id'), 'knowledgebase', ['faq_id'])


def downgrade() -> None:
    """Remove faq_id column from knowledgebase table."""
    op.drop_index(op.f('ix_knowledgebase_faq_id'), table_name='knowledgebase')
    op.drop_column('knowledgebase', 'faq_id')

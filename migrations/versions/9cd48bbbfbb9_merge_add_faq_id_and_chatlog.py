"""merge_add_faq_id_and_chatlog

Revision ID: 9cd48bbbfbb9
Revises: add_faq_id_to_knowledgebase, f1e2d3c4b5a6
Create Date: 2026-05-28 18:46:11.232003

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '9cd48bbbfbb9'
down_revision: Union[str, Sequence[str], None] = ('add_faq_id_to_knowledgebase', 'f1e2d3c4b5a6')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

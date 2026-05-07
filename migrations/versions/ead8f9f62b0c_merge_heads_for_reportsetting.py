"""merge_heads_for_reportsetting

Revision ID: ead8f9f62b0c
Revises: abc123def456, c3d4e5f6a7b8
Create Date: 2026-05-07 22:40:23.920452

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'ead8f9f62b0c'
down_revision: Union[str, Sequence[str], None] = ('abc123def456', 'c3d4e5f6a7b8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass

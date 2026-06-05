"""add_no_answer_and_ticket_flag_to_chatlog

Revision ID: 0288d910ab54
Revises: 9cd48bbbfbb9
Create Date: 2026-06-05 21:19:58.468652

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '0288d910ab54'
down_revision: Union[str, Sequence[str], None] = '9cd48bbbfbb9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('chatlog', sa.Column('no_answer', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.add_column('chatlog', sa.Column('ticket_flag', sa.Boolean(), nullable=False, server_default=sa.text('false')))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('chatlog', 'ticket_flag')
    op.drop_column('chatlog', 'no_answer')
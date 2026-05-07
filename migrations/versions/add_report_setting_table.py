"""add_report_setting_table

Revision ID: abc123def456
Revises: fe2009b2b700
Create Date: 2026-05-07 14:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'abc123def456'
down_revision: Union[str, Sequence[str], None] = 'fe2009b2b700'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('report_setting',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('recipient_email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('period', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('last_sent_at', sa.DateTime(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_report_setting_recipient_email'), 'report_setting', ['recipient_email'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_report_setting_recipient_email'), table_name='report_setting')
    op.drop_table('report_setting')
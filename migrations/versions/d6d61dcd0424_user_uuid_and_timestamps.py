"""user_uuid_and_timestamps

Revision ID: d6d61dcd0424
Revises: 7655d0d2f6ca
Create Date: 2026-04-23 14:42:38.466137

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'd6d61dcd0424'
down_revision: Union[str, Sequence[str], None] = '7655d0d2f6ca'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FK-dependent tables first, then user (IF EXISTS to handle partial states)
    op.execute('DROP TABLE IF EXISTS ticket CASCADE')
    op.execute('DROP TABLE IF EXISTS chatlog CASCADE')
    op.execute('DROP TABLE IF EXISTS "user" CASCADE')

    # Recreate user with UUID PK + timestamps
    op.create_table(
        'user',
        sa.Column('id', sa.UUID(), nullable=False, server_default=sa.text('gen_random_uuid()')),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('hashed_password', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_email', 'user', ['email'], unique=True)

    # Recreate chatlog with UUID FK
    op.create_table(
        'chatlog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('user_query', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('image_query_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('bot_response', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_resolved', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # Recreate ticket with UUID FK
    op.create_table(
        'ticket',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=True),
        sa.Column('user_email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('subject', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('image_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ticket_category', 'ticket', ['category'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_ticket_category', table_name='ticket')
    op.drop_table('ticket')
    op.drop_table('chatlog')
    op.drop_index('ix_user_email', table_name='user')
    op.drop_table('user')

    # Restore original integer-based schema
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('hashed_password', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('full_name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('role', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_user_email', 'user', ['email'], unique=True)

    op.create_table(
        'chatlog',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_query', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('image_query_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('bot_response', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('is_resolved', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_table(
        'ticket',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('user_email', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('subject', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('category', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('image_url', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_ticket_category', 'ticket', ['category'], unique=False)

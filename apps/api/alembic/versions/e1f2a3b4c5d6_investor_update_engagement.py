"""Investor updates: structured sections, metrics snapshot, drafts + view tracking

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('investor_updates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('period_label', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('highlights', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('lowlights', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('asks', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('metrics', sa.JSON(), nullable=True))
        batch_op.add_column(
            sa.Column('status', sa.String(length=12), nullable=False, server_default='published')
        )
        batch_op.add_column(sa.Column('published_at', sa.DateTime(), nullable=True))

    op.create_table(
        'investor_update_views',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('update_id', sa.String(length=32), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('view_count', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('last_viewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['update_id'], ['investor_updates.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_investor_update_views_update_id'),
        'investor_update_views', ['update_id'], unique=False,
    )
    op.create_index(
        op.f('ix_investor_update_views_email'),
        'investor_update_views', ['email'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_investor_update_views_email'), table_name='investor_update_views')
    op.drop_index(op.f('ix_investor_update_views_update_id'), table_name='investor_update_views')
    op.drop_table('investor_update_views')
    with op.batch_alter_table('investor_updates', schema=None) as batch_op:
        batch_op.drop_column('published_at')
        batch_op.drop_column('status')
        batch_op.drop_column('metrics')
        batch_op.drop_column('asks')
        batch_op.drop_column('lowlights')
        batch_op.drop_column('highlights')
        batch_op.drop_column('period_label')

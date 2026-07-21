"""DDQ answer bank: per-fund due-diligence Q&A entries

Revision ID: c5d6e7f8a9b0
Revises: b4c5d6e7f8a9
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c5d6e7f8a9b0'
down_revision: Union[str, Sequence[str], None] = 'b4c5d6e7f8a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'ddq_entries',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False, server_default='General'),
        sa.Column('question', sa.String(length=500), nullable=False),
        sa.Column('answer', sa.Text(), nullable=True),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ddq_entries_fund_id'), 'ddq_entries', ['fund_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_ddq_entries_fund_id'), table_name='ddq_entries')
    op.drop_table('ddq_entries')

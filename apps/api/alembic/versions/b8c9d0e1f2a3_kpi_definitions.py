"""Custom KPI definitions + per-period custom values

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, Sequence[str], None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('portfolio_kpis', schema=None) as batch_op:
        batch_op.add_column(sa.Column('custom', sa.JSON(), nullable=True))

    op.create_table(
        'kpi_definitions',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('key', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('unit', sa.String(length=8), nullable=False, server_default='number'),
        sa.Column('created_by', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('fund_id', 'key'),
    )
    op.create_index(op.f('ix_kpi_definitions_fund_id'), 'kpi_definitions', ['fund_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_kpi_definitions_fund_id'), table_name='kpi_definitions')
    op.drop_table('kpi_definitions')
    with op.batch_alter_table('portfolio_kpis', schema=None) as batch_op:
        batch_op.drop_column('custom')

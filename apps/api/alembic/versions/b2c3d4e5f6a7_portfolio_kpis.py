"""portfolio company KPIs

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'portfolio_kpis',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('investment_id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('period_label', sa.String(length=64), nullable=False),
        sa.Column('as_of', sa.Date(), nullable=False),
        sa.Column('revenue', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('cash', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('monthly_burn', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('headcount', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['investment_id'], ['portfolio_investments.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portfolio_kpis_investment_id'), 'portfolio_kpis', ['investment_id'], unique=False)
    op.create_index(op.f('ix_portfolio_kpis_fund_id'), 'portfolio_kpis', ['fund_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_portfolio_kpis_fund_id'), table_name='portfolio_kpis')
    op.drop_index(op.f('ix_portfolio_kpis_investment_id'), table_name='portfolio_kpis')
    op.drop_table('portfolio_kpis')

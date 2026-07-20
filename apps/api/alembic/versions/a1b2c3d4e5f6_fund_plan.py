"""fund construction plan

Revision ID: a1b2c3d4e5f6
Revises: f4d6c8e0a2b4
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'f4d6c8e0a2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'fund_plans',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('fund_size', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'),
        sa.Column('fund_life_years', sa.Integer(), nullable=False, server_default='10'),
        sa.Column('investment_period_years', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('est_expenses', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'),
        sa.Column('reserve_pct', sa.Numeric(precision=6, scale=4), nullable=False, server_default='0.40'),
        sa.Column('avg_initial_cheque', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'),
        sa.Column('avg_entry_valuation', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'),
        sa.Column('projected_gross_moic', sa.Numeric(precision=6, scale=2), nullable=False, server_default='3'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_fund_plans_fund_id'), 'fund_plans', ['fund_id'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_fund_plans_fund_id'), table_name='fund_plans')
    op.drop_table('fund_plans')

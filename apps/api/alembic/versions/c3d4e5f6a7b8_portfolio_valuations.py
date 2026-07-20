"""SEBI independent portfolio valuations + fund valuation policy

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('funds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('valuer_name', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('valuation_frequency_months', sa.Integer(), nullable=False, server_default='12'))

    op.create_table(
        'portfolio_valuations',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('investment_id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('as_of', sa.Date(), nullable=False),
        sa.Column('value', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('methodology', sa.String(length=64), nullable=False, server_default='ipev_market'),
        sa.Column('valuer', sa.String(length=255), nullable=True),
        sa.Column('is_independent', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['investment_id'], ['portfolio_investments.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_portfolio_valuations_investment_id'), 'portfolio_valuations', ['investment_id'], unique=False)
    op.create_index(op.f('ix_portfolio_valuations_fund_id'), 'portfolio_valuations', ['fund_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_portfolio_valuations_fund_id'), table_name='portfolio_valuations')
    op.drop_index(op.f('ix_portfolio_valuations_investment_id'), table_name='portfolio_valuations')
    op.drop_table('portfolio_valuations')
    with op.batch_alter_table('funds', schema=None) as batch_op:
        batch_op.drop_column('valuation_frequency_months')
        batch_op.drop_column('valuer_name')

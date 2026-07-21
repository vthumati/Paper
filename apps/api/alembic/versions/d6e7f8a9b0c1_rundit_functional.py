"""Follow-on investment rounds, fund expenses, company notes, update audiences

Revision ID: d6e7f8a9b0c1
Revises: c5d6e7f8a9b0
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e7f8a9b0c1'
down_revision: Union[str, Sequence[str], None] = 'c5d6e7f8a9b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'investment_rounds',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('investment_id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('round_label', sa.String(length=64), nullable=True),
        sa.Column('instrument', sa.String(length=32), nullable=False, server_default='equity'),
        sa.Column('amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('invested_on', sa.Date(), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['investment_id'], ['portfolio_investments.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_investment_rounds_investment_id'), 'investment_rounds', ['investment_id'], unique=False)
    op.create_index(op.f('ix_investment_rounds_fund_id'), 'investment_rounds', ['fund_id'], unique=False)

    op.create_table(
        'fund_expenses',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('category', sa.String(length=64), nullable=False, server_default='other'),
        sa.Column('amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_fund_expenses_fund_id'), 'fund_expenses', ['fund_id'], unique=False)

    op.create_table(
        'company_notes',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('investment_id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('body', sa.String(length=2000), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['investment_id'], ['portfolio_investments.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_company_notes_investment_id'), 'company_notes', ['investment_id'], unique=False)
    op.create_index(op.f('ix_company_notes_fund_id'), 'company_notes', ['fund_id'], unique=False)

    with op.batch_alter_table('investor_updates', schema=None) as batch_op:
        batch_op.add_column(sa.Column('audience', sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('investor_updates', schema=None) as batch_op:
        batch_op.drop_column('audience')
    op.drop_index(op.f('ix_company_notes_fund_id'), table_name='company_notes')
    op.drop_index(op.f('ix_company_notes_investment_id'), table_name='company_notes')
    op.drop_table('company_notes')
    op.drop_index(op.f('ix_fund_expenses_fund_id'), table_name='fund_expenses')
    op.drop_table('fund_expenses')
    op.drop_index(op.f('ix_investment_rounds_fund_id'), table_name='investment_rounds')
    op.drop_index(op.f('ix_investment_rounds_investment_id'), table_name='investment_rounds')
    op.drop_table('investment_rounds')

"""KPI reporting requests (investee self-service)

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('portfolio_investments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_email', sa.String(length=255), nullable=True))

    op.create_table(
        'kpi_requests',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('investment_id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('period_label', sa.String(length=64), nullable=False),
        sa.Column('as_of', sa.Date(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('contact_email', sa.String(length=255), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'SUBMITTED', 'ACCEPTED', name='kpirequeststatus'), nullable=False, server_default='PENDING'),
        sa.Column('revenue', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('cash', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('monthly_burn', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('headcount', sa.Integer(), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('kpi_id', sa.String(length=32), nullable=True),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['investment_id'], ['portfolio_investments.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_kpi_requests_investment_id'), 'kpi_requests', ['investment_id'], unique=False)
    op.create_index(op.f('ix_kpi_requests_fund_id'), 'kpi_requests', ['fund_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_kpi_requests_fund_id'), table_name='kpi_requests')
    op.drop_index(op.f('ix_kpi_requests_investment_id'), table_name='kpi_requests')
    op.drop_table('kpi_requests')
    with op.batch_alter_table('portfolio_investments', schema=None) as batch_op:
        batch_op.drop_column('contact_email')

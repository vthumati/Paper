"""fund deal pipeline

Revision ID: b0e2a4c6d8f0
Revises: a9d1f3b5c7e9
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0e2a4c6d8f0'
down_revision: Union[str, Sequence[str], None] = 'a9d1f3b5c7e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'fund_deals',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('sector', sa.String(length=120), nullable=True),
        sa.Column('stage', sa.Enum('SOURCED', 'SCREENING', 'DILIGENCE', 'IC', 'TERM_SHEET', 'INVESTED', 'PASSED', name='dealstage'), nullable=False),
        sa.Column('amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('notes', sa.String(length=2000), nullable=True),
        sa.Column('investment_id', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('fund_deals', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fund_deals_fund_id'), ['fund_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('fund_deals', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fund_deals_fund_id'))
    op.drop_table('fund_deals')

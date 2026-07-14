"""fee charges ledger

Revision ID: a9d1f3b5c7e9
Revises: f8c0e2a4b6d8
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9d1f3b5c7e9'
down_revision: Union[str, Sequence[str], None] = 'f8c0e2a4b6d8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'fee_charges',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('lp_id', sa.String(length=32), nullable=False),
        sa.Column('amount', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('period_label', sa.String(length=64), nullable=False),
        sa.Column('charged_on', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.ForeignKeyConstraint(['lp_id'], ['lps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('fee_charges', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fee_charges_fund_id'), ['fund_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fee_charges_lp_id'), ['lp_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('fee_charges', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fee_charges_lp_id'))
        batch_op.drop_index(batch_op.f('ix_fee_charges_fund_id'))
    op.drop_table('fee_charges')

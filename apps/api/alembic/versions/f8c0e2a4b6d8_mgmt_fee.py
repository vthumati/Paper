"""fund management fee

Revision ID: f8c0e2a4b6d8
Revises: e6b8d0f2a4c6
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f8c0e2a4b6d8'
down_revision: Union[str, Sequence[str], None] = 'e6b8d0f2a4c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('funds', schema=None) as batch_op:
        batch_op.add_column(sa.Column('mgmt_fee_pct', sa.Numeric(precision=6, scale=4), nullable=False, server_default='0.02'))
        batch_op.add_column(sa.Column('fee_basis', sa.String(length=16), nullable=False, server_default='committed'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('funds', schema=None) as batch_op:
        batch_op.drop_column('fee_basis')
        batch_op.drop_column('mgmt_fee_pct')

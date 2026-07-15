"""SPV syndicate flow: deal terms + co-investor status

Revision ID: a8f0c2d4e6b8
Revises: f7d9b1c3e5a7
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a8f0c2d4e6b8'
down_revision: Union[str, Sequence[str], None] = 'f7d9b1c3e5a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('spvs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('carry_pct', sa.Numeric(precision=6, scale=4), nullable=False, server_default='0')
        )
        batch_op.add_column(
            sa.Column('min_ticket', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0')
        )
    with op.batch_alter_table('spv_co_investors', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('status', sa.String(length=16), nullable=False, server_default='invited')
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('spv_co_investors', schema=None) as batch_op:
        batch_op.drop_column('status')
    with op.batch_alter_table('spvs', schema=None) as batch_op:
        batch_op.drop_column('min_ticket')
        batch_op.drop_column('carry_pct')

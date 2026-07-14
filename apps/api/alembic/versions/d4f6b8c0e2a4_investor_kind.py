"""investor kind on instruments and commitments (friends & family)

Revision ID: d4f6b8c0e2a4
Revises: c3e5a7b9d1f2
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f6b8c0e2a4'
down_revision: Union[str, Sequence[str], None] = 'c3e5a7b9d1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('convertible_instruments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('investor_kind', sa.String(length=16), nullable=False, server_default='angel'))

    with op.batch_alter_table('round_commitments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('investor_kind', sa.String(length=16), nullable=False, server_default='institutional'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('round_commitments', schema=None) as batch_op:
        batch_op.drop_column('investor_kind')

    with op.batch_alter_table('convertible_instruments', schema=None) as batch_op:
        batch_op.drop_column('investor_kind')

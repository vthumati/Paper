"""instrument execution flow: agreement + board approval links

Revision ID: c2e4a6b8d0f2
Revises: b9a1d3e5f7c9
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2e4a6b8d0f2'
down_revision: Union[str, Sequence[str], None] = 'b9a1d3e5f7c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('convertible_instruments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('agreement_document_id', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('board_resolution_id', sa.String(length=32), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('convertible_instruments', schema=None) as batch_op:
        batch_op.drop_column('board_resolution_id')
        batch_op.drop_column('agreement_document_id')

"""entity lifecycle stage

Revision ID: c3e5a7b9d1f2
Revises: b1c9d2e4f6a8
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c3e5a7b9d1f2'
down_revision: Union[str, Sequence[str], None] = 'b1c9d2e4f6a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('legal_entities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stage', sa.String(length=16), nullable=False, server_default='inception'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('legal_entities', schema=None) as batch_op:
        batch_op.drop_column('stage')

"""esop grant type: option / rsu / rsa

Revision ID: e1a3c5b7d9f0
Revises: d4f6a8c0b2e4
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1a3c5b7d9f0'
down_revision: Union[str, Sequence[str], None] = 'd4f6a8c0b2e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('esop_grants', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('grant_type', sa.String(length=8), nullable=False, server_default='option')
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('esop_grants', schema=None) as batch_op:
        batch_op.drop_column('grant_type')

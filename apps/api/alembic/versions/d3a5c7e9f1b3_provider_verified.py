"""provider verification flag

Revision ID: d3a5c7e9f1b3
Revises: c1f3b5d7e9a1
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3a5c7e9f1b3'
down_revision: Union[str, Sequence[str], None] = 'c1f3b5d7e9a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('service_providers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('verified', sa.Boolean(), nullable=False, server_default='0'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('service_providers', schema=None) as batch_op:
        batch_op.drop_column('verified')

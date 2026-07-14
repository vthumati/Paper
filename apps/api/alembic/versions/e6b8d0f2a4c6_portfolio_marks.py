"""portfolio mark-to-market

Revision ID: e6b8d0f2a4c6
Revises: d4f6b8c0e2a4
Create Date: 2026-07-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e6b8d0f2a4c6'
down_revision: Union[str, Sequence[str], None] = 'd4f6b8c0e2a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('portfolio_investments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('current_value', sa.Numeric(precision=20, scale=2), nullable=True))
        batch_op.add_column(sa.Column('marked_on', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('portfolio_investments', schema=None) as batch_op:
        batch_op.drop_column('marked_on')
        batch_op.drop_column('current_value')

"""fund waterfall breakdown + anti-dilution terms

Revision ID: b1c9d2e4f6a8
Revises: a64b6c407af7
Create Date: 2026-07-03

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b1c9d2e4f6a8'
down_revision: Union[str, Sequence[str], None] = 'a64b6c407af7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('distributions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('roc_amount', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('pref_amount', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('catchup_amount', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'))

    with op.batch_alter_table('security_classes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('anti_dilution', sa.String(length=16), nullable=False, server_default='none'))
        batch_op.add_column(sa.Column('orig_issue_price', sa.Numeric(precision=18, scale=4), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('security_classes', schema=None) as batch_op:
        batch_op.drop_column('orig_issue_price')
        batch_op.drop_column('anti_dilution')

    with op.batch_alter_table('distributions', schema=None) as batch_op:
        batch_op.drop_column('catchup_amount')
        batch_op.drop_column('pref_amount')
        batch_op.drop_column('roc_amount')

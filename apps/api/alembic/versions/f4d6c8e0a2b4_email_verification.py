"""email verification (proof-of-ownership gate for email-matched access)

Revision ID: f4d6c8e0a2b4
Revises: f3c5e7a9b1d2
Create Date: 2026-07-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4d6c8e0a2b4'
down_revision: Union[str, Sequence[str], None] = 'f3c5e7a9b1d2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None) as b:
        b.add_column(
            sa.Column(
                'email_verified', sa.Boolean(), nullable=False, server_default=sa.false()
            )
        )
        b.add_column(sa.Column('email_verification_token', sa.String(length=64), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as b:
        b.drop_column('email_verification_token')
        b.drop_column('email_verified')

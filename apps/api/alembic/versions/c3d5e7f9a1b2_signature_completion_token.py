"""signature completion token (e-sign hardening)

Revision ID: c3d5e7f9a1b2
Revises: b2c4d6e8f0a1
Create Date: 2026-07-24

"""
import sqlalchemy as sa

from alembic import op

revision = "c3d5e7f9a1b2"
down_revision = "b2c4d6e8f0a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signature_requests",
        sa.Column("completion_token", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signature_requests", "completion_token")

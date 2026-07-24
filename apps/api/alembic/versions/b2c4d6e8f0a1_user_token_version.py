"""user token_version for stateless JWT revocation

Revision ID: b2c4d6e8f0a1
Revises: f8a9b0c1d2e3
Create Date: 2026-07-24

"""
import sqlalchemy as sa

from alembic import op

revision = "b2c4d6e8f0a1"
down_revision = "f8a9b0c1d2e3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("users", "token_version")

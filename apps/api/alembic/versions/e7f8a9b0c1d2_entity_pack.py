"""entity feature pack (starter/growth/scale)

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-07-21

"""
import sqlalchemy as sa

from alembic import op

revision = "e7f8a9b0c1d2"
down_revision = "d6e7f8a9b0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "legal_entities",
        sa.Column("pack", sa.String(length=16), nullable=False, server_default="starter"),
    )


def downgrade() -> None:
    op.drop_column("legal_entities", "pack")

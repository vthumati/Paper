"""esop forfeiture / true-up events

Revision ID: e5f7a9b1c3d5
Revises: c3d5e7f9a1b2
Create Date: 2026-07-24

"""
import sqlalchemy as sa

from alembic import op

revision = "e5f7a9b1c3d5"
down_revision = "c3d5e7f9a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "esop_forfeitures",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("entity_id", sa.String(length=32), nullable=False),
        sa.Column("grant_id", sa.String(length=32), nullable=False),
        sa.Column("stakeholder_id", sa.String(length=32), nullable=False),
        sa.Column("lapsed_quantity", sa.Integer(), nullable=False),
        sa.Column("vested_retained", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["entity_id"], ["legal_entities.id"]),
        sa.ForeignKeyConstraint(["grant_id"], ["esop_grants.id"]),
        sa.ForeignKeyConstraint(["stakeholder_id"], ["stakeholders.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_esop_forfeitures_entity_id", "esop_forfeitures", ["entity_id"])
    op.create_index("ix_esop_forfeitures_grant_id", "esop_forfeitures", ["grant_id"])


def downgrade() -> None:
    op.drop_index("ix_esop_forfeitures_grant_id", table_name="esop_forfeitures")
    op.drop_index("ix_esop_forfeitures_entity_id", table_name="esop_forfeitures")
    op.drop_table("esop_forfeitures")

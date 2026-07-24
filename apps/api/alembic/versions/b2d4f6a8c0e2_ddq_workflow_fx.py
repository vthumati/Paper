"""DDQ workflow fields, portfolio currency, FX rates

Revision ID: b2d4f6a8c0e2
Revises: a1c3e5f7b9d1
Create Date: 2026-07-24

"""
import sqlalchemy as sa

from alembic import op

revision = "b2d4f6a8c0e2"
down_revision = "a1c3e5f7b9d1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ddq_entries", schema=None) as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"))
        batch_op.add_column(sa.Column("assignee", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("reviewer", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("regulator", sa.String(length=8), nullable=False, server_default="none"))
    with op.batch_alter_table("portfolio_investments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("currency", sa.String(length=8), nullable=False, server_default="INR"))

    op.create_table(
        "fx_rates",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("fund_id", sa.String(length=32), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("as_of", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["fund_id"], ["funds.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fx_rates_fund_id", "fx_rates", ["fund_id"])


def downgrade() -> None:
    op.drop_index("ix_fx_rates_fund_id", table_name="fx_rates")
    op.drop_table("fx_rates")
    with op.batch_alter_table("portfolio_investments", schema=None) as batch_op:
        batch_op.drop_column("currency")
    with op.batch_alter_table("ddq_entries", schema=None) as batch_op:
        batch_op.drop_column("regulator")
        batch_op.drop_column("reviewer")
        batch_op.drop_column("assignee")
        batch_op.drop_column("status")

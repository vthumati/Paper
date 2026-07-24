"""portfolio investment -> company entity link

Revision ID: f8a9b0c1d2e3
Revises: e7f8a9b0c1d2
Create Date: 2026-07-21

"""
import sqlalchemy as sa

from alembic import op

revision = "f8a9b0c1d2e3"
down_revision = "e7f8a9b0c1d2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # batch mode so this applies on SQLite too (which can't ALTER-add an FK);
    # transparent (direct ALTER) on Postgres. Matches the other migrations.
    with op.batch_alter_table("portfolio_investments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("company_entity_id", sa.String(length=32), nullable=True))
        batch_op.create_index(
            "ix_portfolio_investments_company_entity_id", ["company_entity_id"]
        )
        batch_op.create_foreign_key(
            "fk_portfolio_investments_company_entity_id",
            "legal_entities",
            ["company_entity_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("portfolio_investments", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_portfolio_investments_company_entity_id", type_="foreignkey"
        )
        batch_op.drop_index("ix_portfolio_investments_company_entity_id")
        batch_op.drop_column("company_entity_id")

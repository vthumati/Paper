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
    op.add_column(
        "portfolio_investments",
        sa.Column("company_entity_id", sa.String(length=32), nullable=True),
    )
    op.create_index(
        "ix_portfolio_investments_company_entity_id",
        "portfolio_investments",
        ["company_entity_id"],
    )
    op.create_foreign_key(
        "fk_portfolio_investments_company_entity_id",
        "portfolio_investments",
        "legal_entities",
        ["company_entity_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_portfolio_investments_company_entity_id", "portfolio_investments", type_="foreignkey"
    )
    op.drop_index("ix_portfolio_investments_company_entity_id", "portfolio_investments")
    op.drop_column("portfolio_investments", "company_entity_id")

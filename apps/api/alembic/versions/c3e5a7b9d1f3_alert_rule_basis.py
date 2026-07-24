"""metric alert rule basis (value | pct_change)

Revision ID: c3e5a7b9d1f3
Revises: b2d4f6a8c0e2
Create Date: 2026-07-24

"""
import sqlalchemy as sa

from alembic import op

revision = "c3e5a7b9d1f3"
down_revision = "b2d4f6a8c0e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("metric_alert_rules", schema=None) as batch_op:
        batch_op.add_column(sa.Column("basis", sa.String(length=12), nullable=False, server_default="value"))


def downgrade() -> None:
    with op.batch_alter_table("metric_alert_rules", schema=None) as batch_op:
        batch_op.drop_column("basis")

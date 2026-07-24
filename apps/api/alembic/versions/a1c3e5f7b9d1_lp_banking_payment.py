"""fund/LP bank details + drawdown payment verification

Revision ID: a1c3e5f7b9d1
Revises: f7a9c1e3d5b7
Create Date: 2026-07-24

"""
import sqlalchemy as sa

from alembic import op

revision = "a1c3e5f7b9d1"
down_revision = "f7a9c1e3d5b7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("funds", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bank_name", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("bank_account", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("bank_ifsc", sa.String(length=16), nullable=True))
    with op.batch_alter_table("lps", schema=None) as batch_op:
        batch_op.add_column(sa.Column("bank_name", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("bank_account", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("bank_ifsc", sa.String(length=16), nullable=True))
    with op.batch_alter_table("drawdown_notices", schema=None) as batch_op:
        batch_op.add_column(sa.Column("payment_ref", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("verified_by", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("drawdown_notices", schema=None) as batch_op:
        batch_op.drop_column("verified_by")
        batch_op.drop_column("payment_ref")
    with op.batch_alter_table("lps", schema=None) as batch_op:
        batch_op.drop_column("bank_ifsc")
        batch_op.drop_column("bank_account")
        batch_op.drop_column("bank_name")
    with op.batch_alter_table("funds", schema=None) as batch_op:
        batch_op.drop_column("bank_ifsc")
        batch_op.drop_column("bank_account")
        batch_op.drop_column("bank_name")

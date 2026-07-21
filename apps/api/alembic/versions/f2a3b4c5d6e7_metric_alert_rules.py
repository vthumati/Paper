"""Metric alert rules: fund-defined thresholds surfacing as portfolio signals

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, Sequence[str], None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'metric_alert_rules',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('metric', sa.String(length=72), nullable=False),
        sa.Column('comparator', sa.String(length=2), nullable=False),
        sa.Column('threshold', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('severity', sa.String(length=8), nullable=False, server_default='warn'),
        sa.Column('created_by', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_metric_alert_rules_fund_id'), 'metric_alert_rules', ['fund_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_metric_alert_rules_fund_id'), table_name='metric_alert_rules')
    op.drop_table('metric_alert_rules')

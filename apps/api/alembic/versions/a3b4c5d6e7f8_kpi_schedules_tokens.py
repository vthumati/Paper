"""KPI request schedules (recurring cadence) + no-login submission tokens

Revision ID: a3b4c5d6e7f8
Revises: f2a3b4c5d6e7
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3b4c5d6e7f8'
down_revision: Union[str, Sequence[str], None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('kpi_requests', schema=None) as batch_op:
        batch_op.add_column(sa.Column('token', sa.String(length=43), nullable=True))
        batch_op.create_unique_constraint('uq_kpi_requests_token', ['token'])

    op.create_table(
        'kpi_request_schedules',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('investment_id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('cadence', sa.String(length=9), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['investment_id'], ['portfolio_investments.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('investment_id'),
    )
    op.create_index(
        op.f('ix_kpi_request_schedules_fund_id'), 'kpi_request_schedules', ['fund_id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_kpi_request_schedules_fund_id'), table_name='kpi_request_schedules')
    op.drop_table('kpi_request_schedules')
    with op.batch_alter_table('kpi_requests', schema=None) as batch_op:
        batch_op.drop_constraint('uq_kpi_requests_token', type_='unique')
        batch_op.drop_column('token')

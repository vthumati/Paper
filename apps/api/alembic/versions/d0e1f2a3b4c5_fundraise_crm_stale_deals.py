"""LP-prospect CRM (activities + follow-up) and deal stale-stage tracking

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, Sequence[str], None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('lp_prospects', schema=None) as batch_op:
        batch_op.add_column(sa.Column('next_followup_on', sa.Date(), nullable=True))
    with op.batch_alter_table('fund_deals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('stage_changed_at', sa.DateTime(), nullable=True))

    op.create_table(
        'lp_prospect_activities',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('prospect_id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('kind', sa.String(length=24), nullable=False, server_default='note'),
        sa.Column('body', sa.String(length=2000), nullable=False),
        sa.Column('occurred_on', sa.Date(), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['prospect_id'], ['lp_prospects.id']),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_lp_prospect_activities_prospect_id'),
        'lp_prospect_activities', ['prospect_id'], unique=False,
    )
    op.create_index(
        op.f('ix_lp_prospect_activities_fund_id'),
        'lp_prospect_activities', ['fund_id'], unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_lp_prospect_activities_fund_id'), table_name='lp_prospect_activities')
    op.drop_index(op.f('ix_lp_prospect_activities_prospect_id'), table_name='lp_prospect_activities')
    op.drop_table('lp_prospect_activities')
    with op.batch_alter_table('fund_deals', schema=None) as batch_op:
        batch_op.drop_column('stage_changed_at')
    with op.batch_alter_table('lp_prospects', schema=None) as batch_op:
        batch_op.drop_column('next_followup_on')

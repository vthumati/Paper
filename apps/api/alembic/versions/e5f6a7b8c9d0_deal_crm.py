"""deal CRM — contacts + activity timeline

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, Sequence[str], None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'deal_contacts',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('deal_id', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=120), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('note', sa.String(length=500), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['deal_id'], ['fund_deals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deal_contacts_deal_id'), 'deal_contacts', ['deal_id'], unique=False)

    op.create_table(
        'deal_activities',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('deal_id', sa.String(length=32), nullable=False),
        sa.Column('kind', sa.String(length=24), nullable=False, server_default='note'),
        sa.Column('body', sa.String(length=2000), nullable=False),
        sa.Column('occurred_on', sa.Date(), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['deal_id'], ['fund_deals.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_deal_activities_deal_id'), 'deal_activities', ['deal_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_deal_activities_deal_id'), table_name='deal_activities')
    op.drop_table('deal_activities')
    op.drop_index(op.f('ix_deal_contacts_deal_id'), table_name='deal_contacts')
    op.drop_table('deal_contacts')

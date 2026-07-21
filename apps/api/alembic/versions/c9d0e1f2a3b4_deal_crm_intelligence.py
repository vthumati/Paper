"""Deal CRM intelligence: source, follow-up date, activity contact link

Revision ID: c9d0e1f2a3b4
Revises: b8c9d0e1f2a3
Create Date: 2026-07-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, Sequence[str], None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('fund_deals', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source', sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column('next_followup_on', sa.Date(), nullable=True))
    with op.batch_alter_table('deal_activities', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contact_id', sa.String(length=32), nullable=True))
        batch_op.create_foreign_key(
            'fk_deal_activities_contact_id', 'deal_contacts', ['contact_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('deal_activities', schema=None) as batch_op:
        batch_op.drop_constraint('fk_deal_activities_contact_id', type_='foreignkey')
        batch_op.drop_column('contact_id')
    with op.batch_alter_table('fund_deals', schema=None) as batch_op:
        batch_op.drop_column('next_followup_on')
        batch_op.drop_column('source')

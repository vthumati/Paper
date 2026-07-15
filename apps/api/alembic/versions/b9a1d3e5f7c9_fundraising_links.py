"""fundraising funnel links

Revision ID: b9a1d3e5f7c9
Revises: a8f0c2d4e6b8
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9a1d3e5f7c9'
down_revision: Union[str, Sequence[str], None] = 'a8f0c2d4e6b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'fundraising_links',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('round_id', sa.String(length=32), nullable=False),
        sa.Column('data_room_id', sa.String(length=32), nullable=True),
        sa.Column('token', sa.String(length=64), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.ForeignKeyConstraint(['round_id'], ['rounds.id']),
        sa.ForeignKeyConstraint(['data_room_id'], ['data_rooms.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('fundraising_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_fundraising_links_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_fundraising_links_round_id'), ['round_id'], unique=True)
        batch_op.create_index(batch_op.f('ix_fundraising_links_token'), ['token'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('fundraising_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_fundraising_links_token'))
        batch_op.drop_index(batch_op.f('ix_fundraising_links_round_id'))
        batch_op.drop_index(batch_op.f('ix_fundraising_links_entity_id'))
    op.drop_table('fundraising_links')



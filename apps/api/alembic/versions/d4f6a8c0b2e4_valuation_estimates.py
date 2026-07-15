"""valuation estimates: self-serve indicative startup valuation

Revision ID: d4f6a8c0b2e4
Revises: c2e4a6b8d0f2
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4f6a8c0b2e4'
down_revision: Union[str, Sequence[str], None] = 'c2e4a6b8d0f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'valuation_estimates',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('label', sa.String(length=120), nullable=False),
        sa.Column('inputs', sa.JSON(), nullable=False),
        sa.Column('results', sa.JSON(), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('valuation_estimates', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_valuation_estimates_entity_id'), ['entity_id'], unique=False
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('valuation_estimates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_valuation_estimates_entity_id'))
    op.drop_table('valuation_estimates')

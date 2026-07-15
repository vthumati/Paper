"""employee exercise requests

Revision ID: f7d9b1c3e5a7
Revises: e5c7a9b1d3f5
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f7d9b1c3e5a7'
down_revision: Union[str, Sequence[str], None] = 'e5c7a9b1d3f5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'exercise_requests',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('grant_id', sa.String(length=32), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('cashless', sa.Boolean(), nullable=False),
        sa.Column('status', sa.Enum('OPEN', 'APPROVED', 'REJECTED', name='exerciserequeststatus'), nullable=False),
        sa.Column('exercise_id', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.ForeignKeyConstraint(['grant_id'], ['esop_grants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('exercise_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_exercise_requests_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_exercise_requests_grant_id'), ['grant_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('exercise_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_exercise_requests_grant_id'))
        batch_op.drop_index(batch_op.f('ix_exercise_requests_entity_id'))
    op.drop_table('exercise_requests')

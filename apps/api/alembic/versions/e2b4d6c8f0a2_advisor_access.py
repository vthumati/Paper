"""advisor access: external professional (law firm / CA / CS) entity access

Revision ID: e2b4d6c8f0a2
Revises: e1a3c5b7d9f0
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2b4d6c8f0a2'
down_revision: Union[str, Sequence[str], None] = 'e1a3c5b7d9f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'advisor_access',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('firm_name', sa.String(length=255), nullable=False),
        sa.Column(
            'role',
            sa.Enum('OWNER', 'ADMIN', 'MEMBER', 'VIEWER', name='role'),
            nullable=False,
        ),
        sa.Column('invited_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('entity_id', 'email', name='uq_advisor_entity_email'),
    )
    with op.batch_alter_table('advisor_access', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_advisor_access_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_advisor_access_email'), ['email'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('advisor_access', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_advisor_access_email'))
        batch_op.drop_index(batch_op.f('ix_advisor_access_entity_id'))
    op.drop_table('advisor_access')

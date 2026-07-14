"""investor consents + secondary sale requests

Revision ID: c1f3b5d7e9a1
Revises: b0e2a4c6d8f0
Create Date: 2026-07-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c1f3b5d7e9a1'
down_revision: Union[str, Sequence[str], None] = 'b0e2a4c6d8f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'investor_consents',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('resolution_id', sa.String(length=32), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'APPROVED', 'REJECTED', name='consentstatus'), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.ForeignKeyConstraint(['resolution_id'], ['resolutions.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('investor_consents', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_investor_consents_email'), ['email'], unique=False)
        batch_op.create_index(batch_op.f('ix_investor_consents_entity_id'), ['entity_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_investor_consents_resolution_id'), ['resolution_id'], unique=False)

    op.create_table(
        'secondary_requests',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('stakeholder_id', sa.String(length=32), nullable=False),
        sa.Column('security_class_id', sa.String(length=32), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('price_per_unit', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('status', sa.Enum('OPEN', 'EXECUTED', 'REJECTED', name='secondarystatus'), nullable=False),
        sa.Column('buyer_stakeholder_id', sa.String(length=32), nullable=True),
        sa.Column('transfer_id', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.ForeignKeyConstraint(['stakeholder_id'], ['stakeholders.id']),
        sa.ForeignKeyConstraint(['security_class_id'], ['security_classes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('secondary_requests', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_secondary_requests_entity_id'), ['entity_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('secondary_requests', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_secondary_requests_entity_id'))
    op.drop_table('secondary_requests')
    with op.batch_alter_table('investor_consents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_investor_consents_resolution_id'))
        batch_op.drop_index(batch_op.f('ix_investor_consents_entity_id'))
        batch_op.drop_index(batch_op.f('ix_investor_consents_email'))
    op.drop_table('investor_consents')

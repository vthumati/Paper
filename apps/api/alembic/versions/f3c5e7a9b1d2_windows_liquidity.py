"""exercise windows + liquidity events / tenders

Revision ID: f3c5e7a9b1d2
Revises: e2b4d6c8f0a2
Create Date: 2026-07-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c5e7a9b1d2'
down_revision: Union[str, Sequence[str], None] = 'e2b4d6c8f0a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TS = sa.text('(CURRENT_TIMESTAMP)')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'exercise_windows',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('opens_on', sa.Date(), nullable=False),
        sa.Column('closes_on', sa.Date(), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=_TS, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('exercise_windows', schema=None) as b:
        b.create_index(b.f('ix_exercise_windows_entity_id'), ['entity_id'], unique=False)

    op.create_table(
        'liquidity_events',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('price_per_share', sa.Numeric(18, 4), nullable=False),
        sa.Column('opens_on', sa.Date(), nullable=False),
        sa.Column('closes_on', sa.Date(), nullable=False),
        sa.Column('status', sa.Enum('OPEN', 'SETTLED', 'CANCELLED', name='liquidityeventstatus'), nullable=False),
        sa.Column('created_by', sa.String(length=32), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=_TS, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('liquidity_events', schema=None) as b:
        b.create_index(b.f('ix_liquidity_events_entity_id'), ['entity_id'], unique=False)

    op.create_table(
        'tenders',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('event_id', sa.String(length=32), nullable=False),
        sa.Column('entity_id', sa.String(length=32), nullable=False),
        sa.Column('stakeholder_id', sa.String(length=32), nullable=False),
        sa.Column('security_class_id', sa.String(length=32), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('SUBMITTED', 'SETTLED', 'WITHDRAWN', name='tenderstatus'), nullable=False),
        sa.Column('buyback_id', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=_TS, nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=_TS, nullable=False),
        sa.ForeignKeyConstraint(['event_id'], ['liquidity_events.id']),
        sa.ForeignKeyConstraint(['entity_id'], ['legal_entities.id']),
        sa.ForeignKeyConstraint(['stakeholder_id'], ['stakeholders.id']),
        sa.ForeignKeyConstraint(['security_class_id'], ['security_classes.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('tenders', schema=None) as b:
        b.create_index(b.f('ix_tenders_event_id'), ['event_id'], unique=False)
        b.create_index(b.f('ix_tenders_entity_id'), ['entity_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('tenders', schema=None) as b:
        b.drop_index(b.f('ix_tenders_entity_id'))
        b.drop_index(b.f('ix_tenders_event_id'))
    op.drop_table('tenders')
    with op.batch_alter_table('liquidity_events', schema=None) as b:
        b.drop_index(b.f('ix_liquidity_events_entity_id'))
    op.drop_table('liquidity_events')
    with op.batch_alter_table('exercise_windows', schema=None) as b:
        b.drop_index(b.f('ix_exercise_windows_entity_id'))
    op.drop_table('exercise_windows')

"""LP fundraising prospects

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'lp_prospects',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('fund_id', sa.String(length=32), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('firm', sa.String(length=255), nullable=True),
        sa.Column('kind', sa.String(length=32), nullable=False, server_default='institutional'),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('stage', sa.Enum('PROSPECT', 'CONTACTED', 'MEETING', 'DILIGENCE', 'SOFT_CIRCLED', 'COMMITTED', 'PASSED', name='lpprospectstage'), nullable=False, server_default='PROSPECT'),
        sa.Column('target_commitment', sa.Numeric(precision=20, scale=2), nullable=False, server_default='0'),
        sa.Column('notes', sa.String(length=2000), nullable=True),
        sa.Column('lp_id', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['fund_id'], ['funds.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_lp_prospects_fund_id'), 'lp_prospects', ['fund_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_lp_prospects_fund_id'), table_name='lp_prospects')
    op.drop_table('lp_prospects')

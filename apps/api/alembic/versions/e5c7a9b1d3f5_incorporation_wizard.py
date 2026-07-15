"""incorporation wizard + new provider categories

Revision ID: e5c7a9b1d3f5
Revises: d3a5c7e9f1b3
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5c7a9b1d3f5'
down_revision: Union[str, Sequence[str], None] = 'd3a5c7e9f1b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OLD_CATEGORIES = ('CS', 'CA', 'LAWYER', 'VALUER', 'RTA', 'FUND_ADMIN')
NEW_CATEGORIES = OLD_CATEGORIES + ('REGISTERED_OFFICE', 'VIRTUAL_CFO')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'incorporations',
        sa.Column('id', sa.String(length=32), nullable=False),
        sa.Column('tenant_id', sa.String(length=32), nullable=False),
        sa.Column('status', sa.Enum('DRAFT', 'DOCS_GENERATED', 'FILED', 'REGISTERED', name='incorporationstatus'), nullable=False),
        sa.Column('name_options', sa.JSON(), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=True),
        sa.Column('entity_type', sa.Enum('PVT_LTD', 'LLP', 'OPC', 'FUND', 'SPV', name='entitytype'), nullable=False),
        sa.Column('state', sa.String(length=64), nullable=False),
        sa.Column('registered_office', sa.Text(), nullable=False),
        sa.Column('authorised_capital', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('paid_up_capital', sa.Numeric(precision=20, scale=2), nullable=False),
        sa.Column('par_value', sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column('fy_end', sa.Date(), nullable=True),
        sa.Column('founders', sa.JSON(), nullable=False),
        sa.Column('srn', sa.String(length=64), nullable=True),
        sa.Column('cin', sa.String(length=32), nullable=True),
        sa.Column('entity_id', sa.String(length=32), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('incorporations', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_incorporations_tenant_id'), ['tenant_id'], unique=False)

    with op.batch_alter_table('service_providers', schema=None) as batch_op:
        batch_op.alter_column(
            'category',
            existing_type=sa.Enum(*OLD_CATEGORIES, name='providercategory'),
            type_=sa.Enum(*NEW_CATEGORIES, name='providercategory'),
            existing_nullable=False,
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('service_providers', schema=None) as batch_op:
        batch_op.alter_column(
            'category',
            existing_type=sa.Enum(*NEW_CATEGORIES, name='providercategory'),
            type_=sa.Enum(*OLD_CATEGORIES, name='providercategory'),
            existing_nullable=False,
        )
    with op.batch_alter_table('incorporations', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_incorporations_tenant_id'))
    op.drop_table('incorporations')

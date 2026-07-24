"""authorised capital, stakeholder residency, meeting attendees + resolution votes

Revision ID: f7a9c1e3d5b7
Revises: e5f7a9b1c3d5
Create Date: 2026-07-24

"""
import sqlalchemy as sa

from alembic import op

revision = "f7a9c1e3d5b7"
down_revision = "e5f7a9b1c3d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("legal_entities", schema=None) as batch_op:
        batch_op.add_column(sa.Column("authorised_capital", sa.Numeric(20, 2), nullable=True))
    with op.batch_alter_table("stakeholders", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("residency", sa.String(length=16), nullable=False, server_default="resident")
        )
        batch_op.add_column(sa.Column("nationality", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("country", sa.String(length=64), nullable=True))

    op.create_table(
        "meeting_attendees",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("meeting_id", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False),
        sa.Column("present", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meeting_attendees_meeting_id", "meeting_attendees", ["meeting_id"])

    op.create_table(
        "resolution_votes",
        sa.Column("id", sa.String(length=32), nullable=False),
        sa.Column("resolution_id", sa.String(length=32), nullable=False),
        sa.Column("voter", sa.String(length=255), nullable=False),
        sa.Column("vote", sa.Enum("FOR", "AGAINST", "ABSTAIN", name="votechoice"), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["resolution_id"], ["resolutions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resolution_votes_resolution_id", "resolution_votes", ["resolution_id"])


def downgrade() -> None:
    op.drop_index("ix_resolution_votes_resolution_id", table_name="resolution_votes")
    op.drop_table("resolution_votes")
    op.drop_index("ix_meeting_attendees_meeting_id", table_name="meeting_attendees")
    op.drop_table("meeting_attendees")
    with op.batch_alter_table("stakeholders", schema=None) as batch_op:
        batch_op.drop_column("country")
        batch_op.drop_column("nationality")
        batch_op.drop_column("residency")
    with op.batch_alter_table("legal_entities", schema=None) as batch_op:
        batch_op.drop_column("authorised_capital")

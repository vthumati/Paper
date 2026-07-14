import datetime
import enum

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class EmploymentType(str, enum.Enum):
    EMPLOYEE = "employee"
    CONTRACTOR = "contractor"
    ADVISOR = "advisor"


class TeamMember(Base, TimestampMixin):
    """A team member (FR-R). Onboarding generates HR-legal documents and links
    a cap-table stakeholder so the person can receive ESOP grants."""

    __tablename__ = "team_members"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    employment_type: Mapped[EmploymentType] = mapped_column(
        Enum(EmploymentType), default=EmploymentType.EMPLOYEE
    )
    joined_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    left_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    stakeholder_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")

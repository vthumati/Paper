import datetime
import enum

from sqlalchemy import Date, Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class ObligationStatus(str, enum.Enum):
    DUE = "due"
    IN_PREP = "in_prep"
    FILED = "filed"
    ACKNOWLEDGED = "acknowledged"


class ComplianceObligation(Base, TimestampMixin):
    """A statutory obligation with a due date (FR-H-1/2). Generated from
    entity facts via the rules registry (ADR-3)."""

    __tablename__ = "compliance_obligations"
    __table_args__ = (
        UniqueConstraint("entity_id", "form_code", "period_label", name="uq_obligation"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    form_code: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(255))
    category: Mapped[str] = mapped_column(String(32))  # ROC / FEMA / TAX
    period_label: Mapped[str] = mapped_column(String(32))
    due_date: Mapped[datetime.date] = mapped_column(Date)
    status: Mapped[ObligationStatus] = mapped_column(
        Enum(ObligationStatus), default=ObligationStatus.DUE
    )
    assignee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    srn: Mapped[str | None] = mapped_column(String(64), nullable=True)

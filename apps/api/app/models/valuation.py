import datetime
import enum
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class ValuationMethod(str, enum.Enum):
    RULE_11UA = "rule_11ua"  # Income-Tax issue pricing
    FEMA = "fema"  # FEMA pricing guidelines (non-residents)
    FAIR_VALUE = "fair_value"  # ESOP perquisite / accounting fair value


class ValuationStatus(str, enum.Enum):
    DRAFT = "draft"
    FINAL = "final"


class ValuationReport(Base, TimestampMixin):
    """A valuation report fixing an FMV per share (FR-L). Linked from rounds,
    ESOP pricing/perquisite, and FEMA filings."""

    __tablename__ = "valuation_reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    method: Mapped[ValuationMethod] = mapped_column(Enum(ValuationMethod))
    valuer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fmv_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    valuation_date: Mapped[datetime.date] = mapped_column(Date)
    valid_until: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    basis: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[ValuationStatus] = mapped_column(
        Enum(ValuationStatus), default=ValuationStatus.FINAL
    )
    created_by: Mapped[str] = mapped_column(String(32))

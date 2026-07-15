import datetime
import enum
from decimal import Decimal

from sqlalchemy import JSON, Date, Enum, ForeignKey, Numeric, String
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


class ValuationEstimate(Base, TimestampMixin):
    """A self-serve indicative valuation (FR-L-2): scorecard / VC-method /
    DCF-lite computed from founder inputs with custom method weighting.
    Indicative only — supporting workpaper for a Rule 11UA engagement, not a
    registered-valuer report. Inputs and results are stored as JSON so the
    method mix can evolve without schema churn."""

    __tablename__ = "valuation_estimates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    label: Mapped[str] = mapped_column(String(120))
    inputs: Mapped[dict] = mapped_column(JSON)
    results: Mapped[dict] = mapped_column(JSON)
    created_by: Mapped[str] = mapped_column(String(32))

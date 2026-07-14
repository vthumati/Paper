import datetime
import enum
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class InstrumentType(str, enum.Enum):
    SAFE = "safe"
    CONVERTIBLE_NOTE = "convertible_note"


class InstrumentStatus(str, enum.Enum):
    OUTSTANDING = "outstanding"
    CONVERTED = "converted"
    CANCELLED = "cancelled"


class ConvertibleInstrument(Base, TimestampMixin):
    """A SAFE or convertible note (FR-C-2/3). Converts to equity at a priced
    round using the lower of the valuation-cap price and the discounted round
    price; notes accrue simple interest."""

    __tablename__ = "convertible_instruments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    investor_name: Mapped[str] = mapped_column(String(255))
    investor_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # who the money is from: friend_family / angel / institutional (Sec 42
    # private-placement offerees are counted regardless of kind)
    investor_kind: Mapped[str] = mapped_column(String(16), default="angel")
    instrument_type: Mapped[InstrumentType] = mapped_column(Enum(InstrumentType))
    principal: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    valuation_cap: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    discount_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    mfn: Mapped[bool] = mapped_column(Boolean, default=False)
    interest_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    issue_date: Mapped[datetime.date] = mapped_column(Date)
    status: Mapped[InstrumentStatus] = mapped_column(
        Enum(InstrumentStatus), default=InstrumentStatus.OUTSTANDING
    )
    converted_shares: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stakeholder_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class DematRecord(Base, TimestampMixin):
    """Dematerialisation / ISIN tracking for a security class (FR-C-9)."""

    __tablename__ = "demat_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    isin: Mapped[str | None] = mapped_column(String(16), nullable=True)
    depository: Mapped[str] = mapped_column(String(16), default="NSDL")  # NSDL / CDSL
    status: Mapped[str] = mapped_column(String(16), default="pending")  # pending / dematerialised

import datetime
import enum

from sqlalchemy import Date, Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from decimal import Decimal

from .base import Base, TimestampMixin, gen_id


class LiquidityEventStatus(str, enum.Enum):
    OPEN = "open"
    SETTLED = "settled"
    CANCELLED = "cancelled"


class TenderStatus(str, enum.Enum):
    SUBMITTED = "submitted"
    SETTLED = "settled"
    WITHDRAWN = "withdrawn"


class LiquidityEvent(Base, TimestampMixin):
    """A company-run liquidity window (FR-C-13): the company offers to buy back
    shares at a fixed price over an open period; holders tender their shares,
    and on settlement each accepted tender becomes a cap-table buyback."""

    __tablename__ = "liquidity_events"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(16), default="buyback")  # buyback / tender
    price_per_share: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    opens_on: Mapped[datetime.date] = mapped_column(Date)
    closes_on: Mapped[datetime.date] = mapped_column(Date)
    status: Mapped[LiquidityEventStatus] = mapped_column(
        Enum(LiquidityEventStatus), default=LiquidityEventStatus.OPEN
    )
    created_by: Mapped[str] = mapped_column(String(32))


class Tender(Base, TimestampMixin):
    """A holder's offer to sell shares into a liquidity event."""

    __tablename__ = "tenders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("liquidity_events.id"), index=True)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    status: Mapped[TenderStatus] = mapped_column(Enum(TenderStatus), default=TenderStatus.SUBMITTED)
    buyback_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

import datetime
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class FinancialSnapshot(Base, TimestampMixin):
    """A monthly financial position for runway/burn tracking (manual entry).
    `period` is the first day of the month it represents."""

    __tablename__ = "financial_snapshots"
    __table_args__ = (UniqueConstraint("entity_id", "period", name="uq_entity_period"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    period: Mapped[datetime.date] = mapped_column(Date)
    cash_balance: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    monthly_burn: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    revenue: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))

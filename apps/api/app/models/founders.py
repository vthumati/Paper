import datetime

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class FounderVesting(Base, TimestampMixin):
    """Reverse-vesting / restricted-stock schedule over a founder's already-issued
    shares (FR-D / FR-C). Unvested shares are subject to repurchase on early exit."""

    __tablename__ = "founder_vesting"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    total_shares: Mapped[int] = mapped_column(Integer)
    cliff_months: Mapped[int] = mapped_column(Integer, default=12)
    total_months: Mapped[int] = mapped_column(Integer, default=48)
    start_date: Mapped[datetime.date] = mapped_column(Date)
    repurchased: Mapped[bool] = mapped_column(Boolean, default=False)

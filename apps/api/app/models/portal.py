import datetime
import enum
from decimal import Decimal

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class InvestorAccess(Base, TimestampMixin):
    """Grants a person (by email) scoped read-only portal access to an entity,
    optionally tied to their cap-table stakeholder so they see their own
    holdings (FR-K-1). Matched to a user by email — no tenant membership."""

    __tablename__ = "investor_access"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    stakeholder_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="invited")
    created_by: Mapped[str] = mapped_column(String(32))


class ConsentStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class InvestorConsent(Base, TimestampMixin):
    """An investor's electronic consent on a resolution (SHA reserved matters,
    FR-K): requested per portal-invited investor, decided in their portal."""

    __tablename__ = "investor_consents"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    resolution_id: Mapped[str] = mapped_column(ForeignKey("resolutions.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    status: Mapped[ConsentStatus] = mapped_column(
        Enum(ConsentStatus), default=ConsentStatus.PENDING
    )
    decided_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)


class SecondaryStatus(str, enum.Enum):
    OPEN = "open"
    EXECUTED = "executed"
    REJECTED = "rejected"


class SecondaryRequest(Base, TimestampMixin):
    """An investor's request to sell shares (FR-E-7). The company exercises
    ROFR by choosing the buyer; approval executes a ledger transfer."""

    __tablename__ = "secondary_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    stakeholder_id: Mapped[str] = mapped_column(ForeignKey("stakeholders.id"))
    security_class_id: Mapped[str] = mapped_column(ForeignKey("security_classes.id"))
    quantity: Mapped[int] = mapped_column(Integer)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 4))
    status: Mapped[SecondaryStatus] = mapped_column(
        Enum(SecondaryStatus), default=SecondaryStatus.OPEN
    )
    buyer_stakeholder_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    transfer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class InvestorUpdate(Base, TimestampMixin):
    """A periodic update published by the company/fund to its investors (FR-K-2).
    Extended (Visible-style): structured sections, a metrics snapshot captured
    at publish time, and a draft -> published lifecycle."""

    __tablename__ = "investor_updates"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    period_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    highlights: Mapped[str | None] = mapped_column(Text, nullable=True)
    lowlights: Mapped[str | None] = mapped_column(Text, nullable=True)
    asks: Mapped[str | None] = mapped_column(Text, nullable=True)
    metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="published")
    published_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[str] = mapped_column(String(32))


class InvestorUpdateView(Base, TimestampMixin):
    """A recipient's engagement with a published update: one row per
    (update, viewer email), counting repeat opens (FR-K-2)."""

    __tablename__ = "investor_update_views"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    update_id: Mapped[str] = mapped_column(ForeignKey("investor_updates.id"), index=True)
    email: Mapped[str] = mapped_column(String(255), index=True)
    view_count: Mapped[int] = mapped_column(Integer, default=1)
    last_viewed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

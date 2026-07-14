import datetime
import enum

from sqlalchemy import Date, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class SubscriptionTier(str, enum.Enum):
    BASIC = "basic"
    GROWTH = "growth"
    SCALE = "scale"


class AuditType(str, enum.Enum):
    CORPORATE_AUDIT = "corporate_audit"
    PRE_DILIGENCE = "pre_diligence"
    CLEANUP = "cleanup"


class AuditStatus(str, enum.Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class AdminSubscription(Base, TimestampMixin):
    """Managed Corporate Administration subscription (FR-P), one per entity.
    Optionally serviced by a ServiceProvider from the partner network."""

    __tablename__ = "admin_subscriptions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), unique=True, index=True)
    tier: Mapped[SubscriptionTier] = mapped_column(Enum(SubscriptionTier))
    status: Mapped[str] = mapped_column(String(16), default="active")
    provider_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str] = mapped_column(String(32))

    touchpoints: Mapped[list["TouchpointMeeting"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan", order_by="TouchpointMeeting.date"
    )
    audits: Mapped[list["AuditEngagement"]] = relationship(
        back_populates="subscription", cascade="all, delete-orphan"
    )


class TouchpointMeeting(Base, TimestampMixin):
    __tablename__ = "admin_touchpoints"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("admin_subscriptions.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    attendee: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    subscription: Mapped[AdminSubscription] = relationship(back_populates="touchpoints")


class AuditEngagement(Base, TimestampMixin):
    __tablename__ = "admin_audits"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    subscription_id: Mapped[str] = mapped_column(ForeignKey("admin_subscriptions.id"), index=True)
    type: Mapped[AuditType] = mapped_column(Enum(AuditType))
    period_label: Mapped[str] = mapped_column(String(32))
    status: Mapped[AuditStatus] = mapped_column(Enum(AuditStatus), default=AuditStatus.SCHEDULED)
    findings: Mapped[str | None] = mapped_column(Text, nullable=True)

    subscription: Mapped[AdminSubscription] = relationship(back_populates="audits")

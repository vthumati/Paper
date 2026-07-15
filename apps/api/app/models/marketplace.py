import enum

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class ProviderCategory(str, enum.Enum):
    CS = "cs"
    CA = "ca"
    LAWYER = "lawyer"
    VALUER = "valuer"
    RTA = "rta"
    FUND_ADMIN = "fund_admin"


class EngagementStatus(str, enum.Enum):
    REQUESTED = "requested"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    DELIVERED = "delivered"
    CLOSED = "closed"


class ServiceProvider(Base, TimestampMixin):
    """A vetted professional/firm in the curated partner network (FR-O-1).
    Platform-level directory, not tenant-scoped."""

    __tablename__ = "service_providers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    name: Mapped[str] = mapped_column(String(255))
    category: Mapped[ProviderCategory] = mapped_column(Enum(ProviderCategory))
    firm: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # anyone may register; only platform-verified providers can be engaged
    verified: Mapped[bool] = mapped_column(Boolean, default=False)


class ServiceEngagement(Base, TimestampMixin):
    """A tenant engaging a provider in-context for an entity (FR-O-2)."""

    __tablename__ = "service_engagements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    provider_id: Mapped[str] = mapped_column(ForeignKey("service_providers.id"))
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[EngagementStatus] = mapped_column(
        Enum(EngagementStatus), default=EngagementStatus.REQUESTED
    )
    deliverable_doc_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_by: Mapped[str] = mapped_column(String(32))

import datetime
import enum
from decimal import Decimal

from sqlalchemy import Boolean, Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class SignificantBeneficialOwner(Base, TimestampMixin):
    """Register of Significant Beneficial Owners (SBO / Form BEN-2)."""

    __tablename__ = "sbo_register"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    pan: Mapped[str | None] = mapped_column(String(16), nullable=True)
    percentage: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    nature: Mapped[str | None] = mapped_column(String(255), nullable=True)


class Charge(Base, TimestampMixin):
    """Register of Charges (charges created over company assets, e.g. loans)."""

    __tablename__ = "charges_register"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    holder: Mapped[str] = mapped_column(String(255))  # charge holder / lender
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    charge_type: Mapped[str] = mapped_column(String(120), default="hypothecation")
    created_on: Mapped[datetime.date] = mapped_column(Date)
    satisfied: Mapped[bool] = mapped_column(Boolean, default=False)


class RegistrationKind(str, enum.Enum):
    GST = "gst"
    PROFESSIONAL_TAX = "professional_tax"
    SHOPS_ESTABLISHMENT = "shops_establishment"
    PF = "pf"
    ESIC = "esic"


class Registration(Base, TimestampMixin):
    """Multi-state / multi-jurisdiction registration (India analogue of foreign
    entity qualification, FR-B-8)."""

    __tablename__ = "registrations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    kind: Mapped[RegistrationKind] = mapped_column(Enum(RegistrationKind))
    state: Mapped[str] = mapped_column(String(64))
    number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="active")

import datetime
import enum

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class RecognitionStatus(str, enum.Enum):
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    RECOGNISED = "recognised"
    REJECTED = "rejected"


class BenefitType(str, enum.Enum):
    SECTION_80IAC = "section_80iac"  # 3-year tax holiday
    ANGEL_TAX_EXEMPTION = "angel_tax_56_2_viib"  # exemption u/s 56(2)(viib)


class BenefitStatus(str, enum.Enum):
    NOT_APPLIED = "not_applied"
    APPLIED = "applied"
    APPROVED = "approved"
    REJECTED = "rejected"


class StartupRecognition(Base, TimestampMixin):
    """DPIIT Startup India recognition for an entity (FR-B-6). One per entity."""

    __tablename__ = "startup_recognition"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), unique=True, index=True)
    status: Mapped[RecognitionStatus] = mapped_column(
        Enum(RecognitionStatus), default=RecognitionStatus.APPLIED
    )
    dpiit_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    recognised_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    valid_until: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)


class TaxBenefitApplication(Base, TimestampMixin):
    """A startup tax-benefit application: 80-IAC holiday or angel-tax exemption."""

    __tablename__ = "tax_benefit_applications"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    type: Mapped[BenefitType] = mapped_column(Enum(BenefitType))
    status: Mapped[BenefitStatus] = mapped_column(Enum(BenefitStatus), default=BenefitStatus.APPLIED)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)

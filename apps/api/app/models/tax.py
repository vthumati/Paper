import datetime
import enum
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class TaxRecordType(str, enum.Enum):
    GST = "gst"
    TDS = "tds"
    FORM16 = "form16"
    ITR = "itr"
    OTHER = "other"


class TaxRecord(Base, TimestampMixin):
    """Tax-records vault entry (FR-T-4)."""

    __tablename__ = "tax_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    type: Mapped[TaxRecordType] = mapped_column(Enum(TaxRecordType))
    period_label: Mapped[str] = mapped_column(String(32))
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    filed_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

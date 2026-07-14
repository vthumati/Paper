import datetime
import enum

from sqlalchemy import Date, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class EntityType(str, enum.Enum):
    PVT_LTD = "pvt_ltd"
    LLP = "llp"
    OPC = "opc"
    FUND = "fund"
    SPV = "spv"


class LegalEntity(Base, TimestampMixin):
    """The regulated subject (company/fund/SPV) — hub of the data model.

    See REQUIREMENTS.md §6.3 and HLD §4 (Entity bounded context).
    """

    __tablename__ = "legal_entities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    type: Mapped[EntityType] = mapped_column(Enum(EntityType), default=EntityType.PVT_LTD)
    cin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(16), nullable=True)
    incorporation_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # Lifecycle stage (companies only): inception / seed / series / ipo.
    # Drives the guided checklist and which features are surfaced (app/stages.py).
    stage: Mapped[str] = mapped_column(String(16), default="inception")

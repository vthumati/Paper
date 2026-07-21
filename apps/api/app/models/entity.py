import datetime
import enum
from decimal import Decimal

from sqlalchemy import JSON, Date, Enum, ForeignKey, Numeric, String, Text
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
    # Drives the guided "what to do now" checklist (app/stages.py).
    stage: Mapped[str] = mapped_column(String(16), default="inception")
    # Feature pack (companies only): starter / growth / scale — the commercial
    # tier that decides which tabs and feature-parts are visible (app/stages.py).
    pack: Mapped[str] = mapped_column(String(16), default="starter")


class IncorporationStatus(str, enum.Enum):
    DRAFT = "draft"
    DOCS_GENERATED = "docs_generated"
    FILED = "filed"
    REGISTERED = "registered"


class Incorporation(Base, TimestampMixin):
    """A guided incorporation (FR-B, the Atlas-style wizard): one intake →
    filing pack (SPICe+/eMoA/eAoA) against a pre-registration entity → SRN →
    CIN, at which point founder shares are allotted, directors registered and
    the compliance calendar generated."""

    __tablename__ = "incorporations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id"), index=True)
    status: Mapped[IncorporationStatus] = mapped_column(
        Enum(IncorporationStatus), default=IncorporationStatus.DRAFT
    )
    name_options: Mapped[list] = mapped_column(JSON)  # RUN candidates, preferred first
    company_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_type: Mapped[EntityType] = mapped_column(Enum(EntityType), default=EntityType.PVT_LTD)
    state: Mapped[str] = mapped_column(String(64))
    registered_office: Mapped[str] = mapped_column(Text)
    authorised_capital: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    paid_up_capital: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    par_value: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("10"))
    fy_end: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # [{name, email?, din?, shares, is_director}]
    founders: Mapped[list] = mapped_column(JSON)
    srn: Mapped[str | None] = mapped_column(String(64), nullable=True)
    cin: Mapped[str | None] = mapped_column(String(32), nullable=True)
    entity_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

import datetime
import enum
from decimal import Decimal

from sqlalchemy import Date, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin, gen_id


class PipelineStage(str, enum.Enum):
    CONTACTED = "contacted"
    MEETING = "meeting"
    DILIGENCE = "diligence"
    TERM_SHEET = "term_sheet"
    COMMITTED = "committed"
    PASSED = "passed"


class ProspectInvestor(Base, TimestampMixin):
    """A prospective investor in the fundraising pipeline / CRM (FR-E-1).
    Optionally linked to a round; can be converted into a commitment."""

    __tablename__ = "prospect_investors"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    firm: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stage: Mapped[PipelineStage] = mapped_column(Enum(PipelineStage), default=PipelineStage.CONTACTED)
    check_size: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    round_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_contact: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    commitment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)

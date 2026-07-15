import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class SPV(Base, TimestampMixin):
    """A single-deal co-investment vehicle (HLD §S). Reuses the issuance
    ledger: its combined position sweeps into the portfolio company's cap
    table as one ENTITY stakeholder (FR-S-2)."""

    __tablename__ = "spvs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), unique=True, index=True)
    sponsor: Mapped[str] = mapped_column(String(255))
    target_company: Mapped[str] = mapped_column(String(255))
    structure: Mapped[str] = mapped_column(String(32), default="llp")
    portco_entity_id: Mapped[str | None] = mapped_column(
        ForeignKey("legal_entities.id"), nullable=True
    )
    # deal economics (FR-S-4): carry mirrors into the fund profile on this
    # entity; min_ticket gates portal commitments
    carry_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0"))
    min_ticket: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    created_by: Mapped[str] = mapped_column(String(32))

    co_investors: Mapped[list["CoInvestor"]] = relationship(
        back_populates="spv", cascade="all, delete-orphan"
    )


class CoInvestor(Base, TimestampMixin):
    __tablename__ = "spv_co_investors"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    spv_id: Mapped[str] = mapped_column(ForeignKey("spvs.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commitment: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    contributed: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    # syndicate flow (FR-S-3): invited -> committed -> funded
    status: Mapped[str] = mapped_column(String(16), default="invited")

    spv: Mapped[SPV] = relationship(back_populates="co_investors")


class SPVInvestment(Base, TimestampMixin):
    __tablename__ = "spv_investments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    spv_id: Mapped[str] = mapped_column(ForeignKey("spvs.id"), index=True)
    portco_entity_id: Mapped[str] = mapped_column(String(32))
    security_class_id: Mapped[str] = mapped_column(String(32))
    stakeholder_id: Mapped[str] = mapped_column(String(32))
    quantity: Mapped[int] = mapped_column(Integer)
    price_per_unit: Mapped[Decimal] = mapped_column(Numeric(18, 4), default=Decimal("0"))
    issuance_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    date: Mapped[datetime.date] = mapped_column(Date)

import datetime
import enum
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class SebiCategory(str, enum.Enum):
    CAT_I = "I"
    CAT_II = "II"
    CAT_III = "III"


class DistributionKind(str, enum.Enum):
    RETURN_OF_CAPITAL = "return_of_capital"
    PROFIT = "profit"


class Fund(Base, TimestampMixin):
    """A SEBI AIF, specialising a fund-type LegalEntity (HLD §J / REQUIREMENTS §6.8)."""

    __tablename__ = "funds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), unique=True, index=True)
    sebi_category: Mapped[SebiCategory] = mapped_column(Enum(SebiCategory))
    structure: Mapped[str] = mapped_column(String(32), default="trust")  # trust/llp/company
    currency: Mapped[str] = mapped_column(String(8), default="INR")
    target_corpus: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    carry_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.20"))
    hurdle_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.08"))
    # management fee: simple annual accrual of mgmt_fee_pct on the fee basis
    # ("committed" from each LP's admission; "drawn" from each paid drawdown)
    mgmt_fee_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.02"))
    fee_basis: Mapped[str] = mapped_column(String(16), default="committed")
    created_by: Mapped[str] = mapped_column(String(32))

    lps: Mapped[list["LP"]] = relationship(back_populates="fund", cascade="all, delete-orphan")


class LP(Base, TimestampMixin):
    """Limited partner / contributor with a capital commitment."""

    __tablename__ = "lps"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    commitment: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))

    fund: Mapped[Fund] = relationship(back_populates="lps")


class CapitalCall(Base, TimestampMixin):
    __tablename__ = "capital_calls"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    call_no: Mapped[int] = mapped_column(Integer)
    pct: Mapped[Decimal] = mapped_column(Numeric(6, 4))  # fraction of commitment, e.g. 0.25
    purpose: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

    notices: Mapped[list["DrawdownNotice"]] = relationship(cascade="all, delete-orphan")


class DrawdownNotice(Base, TimestampMixin):
    """Per-LP slice of a capital call (append-only; paid-in is the sum of paid notices)."""

    __tablename__ = "drawdown_notices"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    call_id: Mapped[str] = mapped_column(ForeignKey("capital_calls.id"), index=True)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    lp_id: Mapped[str] = mapped_column(ForeignKey("lps.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    paid: Mapped[bool] = mapped_column(Boolean, default=False)
    paid_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)


class Distribution(Base, TimestampMixin):
    __tablename__ = "distributions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    dist_no: Mapped[int] = mapped_column(Integer)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    kind: Mapped[DistributionKind] = mapped_column(Enum(DistributionKind))
    carry_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    # waterfall breakdown of this distribution (FR-J-5): LP return of capital,
    # LP preferred return, and the GP catch-up portion of carry_amount.
    roc_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    pref_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    catchup_amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)


class LPDistribution(Base, TimestampMixin):
    __tablename__ = "lp_distributions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    distribution_id: Mapped[str] = mapped_column(ForeignKey("distributions.id"), index=True)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    lp_id: Mapped[str] = mapped_column(ForeignKey("lps.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))


class DealStage(str, enum.Enum):
    SOURCED = "sourced"
    SCREENING = "screening"
    DILIGENCE = "diligence"
    IC = "ic"
    TERM_SHEET = "term_sheet"
    INVESTED = "invested"
    PASSED = "passed"


class Deal(Base, TimestampMixin):
    """Fund-side deal pipeline (the GP mirror of the startup investor CRM):
    sourced → screening → diligence → IC → term sheet → invested/passed.
    Investing converts the deal into a PortfolioInvestment."""

    __tablename__ = "fund_deals"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(120), nullable=True)
    stage: Mapped[DealStage] = mapped_column(Enum(DealStage), default=DealStage.SOURCED)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    investment_id: Mapped[str | None] = mapped_column(String(32), nullable=True)


class FeeCharge(Base, TimestampMixin):
    """A management fee actually charged to an LP (the accrual crystallised).
    Append-only; 'fees charged' in capital accounts is the sum of these."""

    __tablename__ = "fee_charges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    lp_id: Mapped[str] = mapped_column(ForeignKey("lps.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    period_label: Mapped[str] = mapped_column(String(64))
    charged_on: Mapped[datetime.date] = mapped_column(Date)


class PortfolioInvestment(Base, TimestampMixin):
    __tablename__ = "portfolio_investments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    instrument: Mapped[str] = mapped_column(String(32), default="equity")
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    ownership_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    invested_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # mark-to-market: latest fair value of the position (NAV input); null = unmarked
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    marked_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)

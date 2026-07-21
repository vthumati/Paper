import datetime
import enum
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
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
    # SEBI independent-valuation policy (FR-J-15): the appointed independent
    # valuer and how often portfolio holdings must be revalued.
    valuer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    valuation_frequency_months: Mapped[int] = mapped_column(Integer, default=12)
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


class LPProspectStage(str, enum.Enum):
    PROSPECT = "prospect"
    CONTACTED = "contacted"
    MEETING = "meeting"
    DILIGENCE = "diligence"
    SOFT_CIRCLED = "soft_circled"
    COMMITTED = "committed"
    PASSED = "passed"


class LPProspect(Base, TimestampMixin):
    """A prospective LP in the fund's own fundraise (GP raising capital) — the
    pipeline that precedes an LP commitment. Converting a prospect creates an LP."""

    __tablename__ = "lp_prospects"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    firm: Mapped[str | None] = mapped_column(String(255), nullable=True)
    kind: Mapped[str] = mapped_column(String(32), default="institutional")
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    stage: Mapped[LPProspectStage] = mapped_column(
        Enum(LPProspectStage), default=LPProspectStage.PROSPECT
    )
    target_commitment: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    notes: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    lp_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # set on convert
    # next follow-up; overdue prospects surface in the pipeline + Tasks hub
    next_followup_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)


class LPProspectActivity(Base, TimestampMixin):
    """A dated touchpoint on an LP prospect (mirrors DealActivity) — the
    fundraise relationship timeline. Append-only."""

    __tablename__ = "lp_prospect_activities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    prospect_id: Mapped[str] = mapped_column(ForeignKey("lp_prospects.id"), index=True)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="note")  # note/meeting/call/email/other
    body: Mapped[str] = mapped_column(String(2000))
    occurred_on: Mapped[datetime.date] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(String(32))


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
    # LP self-service: the LP saw the notice in their portal and confirmed it
    acknowledged_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)


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
    # who referred the deal (person/firm) — feeds "top deal sources" (FR-J-17)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # next follow-up date; overdue follow-ups surface in the pipeline + Tasks hub
    next_followup_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # when the deal last moved stage (falls back to created_at) — stale detection
    stage_changed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)


class DealContact(Base, TimestampMixin):
    """A person associated with a deal (founder, adviser, co-investor) — the
    relationship side of the GP deal CRM."""

    __tablename__ = "deal_contacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    deal_id: Mapped[str] = mapped_column(ForeignKey("fund_deals.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class DealActivity(Base, TimestampMixin):
    """A dated touchpoint on a deal (note / meeting / call / email) — the deal's
    activity timeline. Append-only."""

    __tablename__ = "deal_activities"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    deal_id: Mapped[str] = mapped_column(ForeignKey("fund_deals.id"), index=True)
    kind: Mapped[str] = mapped_column(String(24), default="note")  # note/meeting/call/email/other
    body: Mapped[str] = mapped_column(String(2000))
    occurred_on: Mapped[datetime.date] = mapped_column(Date)
    created_by: Mapped[str] = mapped_column(String(32))
    # optional attribution to a deal contact — drives relationship strength
    contact_id: Mapped[str | None] = mapped_column(
        ForeignKey("deal_contacts.id"), nullable=True
    )


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


class FundPlan(Base, TimestampMixin):
    """Fund construction / forecast model (one per fund). Inputs for the
    portfolio-construction plan; fee % and carry % are read from the Fund so
    they stay a single source of truth. Everything derived (investable capital,
    reserves, #deals, projected returns, pacing) is computed, never stored."""

    __tablename__ = "fund_plans"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), unique=True, index=True)
    fund_size: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    fund_life_years: Mapped[int] = mapped_column(Integer, default=10)
    investment_period_years: Mapped[int] = mapped_column(Integer, default=4)
    est_expenses: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    reserve_pct: Mapped[Decimal] = mapped_column(Numeric(6, 4), default=Decimal("0.40"))
    avg_initial_cheque: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    avg_entry_valuation: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    projected_gross_moic: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("3"))


class PortfolioKPI(Base, TimestampMixin):
    """A period of operating KPIs reported by a portfolio company (Carta-style
    portfolio monitoring). Append-only; the latest period (by as_of) drives the
    dashboard, and runway / growth are derived, never stored."""

    __tablename__ = "portfolio_kpis"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    investment_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_investments.id"), index=True
    )
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    period_label: Mapped[str] = mapped_column(String(64))  # e.g. "FY26 Q1", "Jun 2026"
    as_of: Mapped[datetime.date] = mapped_column(Date)  # orders periods
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    cash: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    monthly_burn: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # fund-defined custom metrics (FR-J-23), keyed by KPIDefinition.key
    custom: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class KPIDefinition(Base, TimestampMixin):
    """A fund-defined custom metric collected alongside the core KPIs
    (Vestberry-style custom KPIs, incl. ESG presets). Values are stored per
    period in PortfolioKPI.custom under this definition's `key`."""

    __tablename__ = "kpi_definitions"
    __table_args__ = (UniqueConstraint("fund_id", "key"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    key: Mapped[str] = mapped_column(String(64))
    label: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(8), default="number")  # inr | number | pct
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class DDQEntry(Base, TimestampMixin):
    """One question-and-answer in the fund's due-diligence answer bank
    (Visible-style DDQ support): answered once, reused for every LP's
    questionnaire and exportable as a DDQ document."""

    __tablename__ = "ddq_entries"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    category: Mapped[str] = mapped_column(String(64), default="General")
    question: Mapped[str] = mapped_column(String(500))
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(32))


class MetricAlertRule(Base, TimestampMixin):
    """A fund-defined performance threshold on a tracked metric (Visible-style
    metric alerts). Evaluated on read against each company's latest reported
    period; breaches surface as portfolio signals."""

    __tablename__ = "metric_alert_rules"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    metric: Mapped[str] = mapped_column(String(72))  # core key or custom.<key>
    comparator: Mapped[str] = mapped_column(String(2))  # lt | gt
    threshold: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    severity: Mapped[str] = mapped_column(String(8), default="warn")  # high | warn
    created_by: Mapped[str | None] = mapped_column(String(32), nullable=True)


class PortfolioValuation(Base, TimestampMixin):
    """An independent valuation of a portfolio holding (SEBI AIF requirement).
    Append-only history; the latest by as_of becomes the holding's mark
    (PortfolioInvestment.current_value) so NAV / SoI / performance stay in sync."""

    __tablename__ = "portfolio_valuations"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    investment_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_investments.id"), index=True
    )
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    as_of: Mapped[datetime.date] = mapped_column(Date)
    value: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    methodology: Mapped[str] = mapped_column(String(64), default="ipev_market")
    valuer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_independent: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)


class PortfolioInvestment(Base, TimestampMixin):
    __tablename__ = "portfolio_investments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True)  # segment tag
    instrument: Mapped[str] = mapped_column(String(32), default="equity")
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2), default=Decimal("0"))
    ownership_pct: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=Decimal("0"))
    invested_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # mark-to-market: latest fair value of the position (NAV input); null = unmarked
    current_value: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    marked_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    # reporting contact at the company — receives KPI requests in their portal
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)


class InvestmentRound(Base, TimestampMixin):
    """A follow-on cheque into an existing portfolio company (Rundit-style
    per-round investment history). The parent PortfolioInvestment.amount stays
    the running total cost, so SOI / NAV / financials are unchanged."""

    __tablename__ = "investment_rounds"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    investment_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_investments.id"), index=True
    )
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    round_label: Mapped[str | None] = mapped_column(String(64), nullable=True)
    instrument: Mapped[str] = mapped_column(String(32), default="equity")
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    invested_on: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(32))


class FundExpense(Base, TimestampMixin):
    """An actual fund expense (audit, legal, admin …) — feeds the fund
    financial statements alongside fees and carry."""

    __tablename__ = "fund_expenses"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    date: Mapped[datetime.date] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(64), default="other")
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_by: Mapped[str] = mapped_column(String(32))


class CompanyNote(Base, TimestampMixin):
    """An internal team comment on a portfolio company (Rundit-style
    collaboration) — never shown to LPs or the company."""

    __tablename__ = "company_notes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    investment_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_investments.id"), index=True
    )
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    body: Mapped[str] = mapped_column(String(2000))
    created_by: Mapped[str] = mapped_column(String(32))


class KPIRequestStatus(str, enum.Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"


class KPIRequest(Base, TimestampMixin):
    """A request for one period of KPIs from a portfolio company (Vestberry-style
    investee self-reporting). The contact submits values from their portal; the GP
    accepts them into a PortfolioKPI (or reopens for resubmission)."""

    __tablename__ = "kpi_requests"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    investment_id: Mapped[str] = mapped_column(
        ForeignKey("portfolio_investments.id"), index=True
    )
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    period_label: Mapped[str] = mapped_column(String(64))
    as_of: Mapped[datetime.date] = mapped_column(Date)
    due_date: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    contact_email: Mapped[str] = mapped_column(String(255))
    status: Mapped[KPIRequestStatus] = mapped_column(
        Enum(KPIRequestStatus), default=KPIRequestStatus.PENDING
    )
    # values as submitted by the company (accepted into a PortfolioKPI by the GP)
    revenue: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    cash: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    monthly_burn: Mapped[Decimal | None] = mapped_column(Numeric(20, 2), nullable=True)
    headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submitted_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)
    kpi_id: Mapped[str | None] = mapped_column(String(32), nullable=True)  # set on accept
    # no-login submission: a secret link token the contact can use without an account
    token: Mapped[str | None] = mapped_column(String(43), nullable=True, unique=True)
    created_by: Mapped[str] = mapped_column(String(32))


class KPIRequestSchedule(Base, TimestampMixin):
    """A recurring KPI-request cadence per portfolio company (Visible-style
    scheduled Requests). Materialised on read: opening the requests list
    creates the request for the last completed period if it doesn't exist."""

    __tablename__ = "kpi_request_schedules"
    __table_args__ = (UniqueConstraint("investment_id"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    investment_id: Mapped[str] = mapped_column(ForeignKey("portfolio_investments.id"))
    fund_id: Mapped[str] = mapped_column(ForeignKey("funds.id"), index=True)
    cadence: Mapped[str] = mapped_column(String(9))  # monthly | quarterly
    created_by: Mapped[str] = mapped_column(String(32))

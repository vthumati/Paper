import csv
import datetime
import io

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (
    DealCtx,
    EntityCtx,
    FundCtx,
    deal_ctx,
    entity_ctx,
    fund_ctx,
    get_current_user,
    require_write,
)
from ..models.fund import (
    CapitalCall,
    Deal,
    DealActivity,
    DealContact,
    DealStage,
    Distribution,
    DrawdownNotice,
    FeeCharge,
    Fund,
    LP,
    LPDistribution,
    LPProspect,
    LPProspectActivity,
    PortfolioInvestment,
    PortfolioKPI,
)
from ..services.money import q
from ..models.entity import EntityType
from ..models.finance import FinancialSnapshot
from ..models.identity import Membership, User
from decimal import Decimal, InvalidOperation

from ..schemas import (
    CapitalCallIn,
    CapitalCallOut,
    CompanyNoteIn,
    ComplianceGenerateIn,
    DealActivityIn,
    DealContactIn,
    DealFollowupIn,
    DealIn,
    DealsImportIn,
    DealInvestIn,
    DealOut,
    DealStageIn,
    FundExpenseIn,
    InvestmentRoundIn,
    DistributionIn,
    DistributionOut,
    DocumentOut,
    DrawdownNoticeOut,
    FundIn,
    FundOut,
    FundPlanIn,
    FundValuationPolicyIn,
    DDQEntryIn,
    DDQEntryUpdateIn,
    KPIDefinitionIn,
    KPIRequestIn,
    KPIRequestSubmitIn,
    KPIScheduleIn,
    MetricAlertRuleIn,
    LPIn,
    LPOut,
    LPProspectActivityIn,
    LPProspectConvertIn,
    LPProspectIn,
    LPProspectStageIn,
    LPReportIn,
    PortfolioValuationIn,
    PortfolioIn,
    PortfolioKPIIn,
    PortfolioMarkIn,
    PortfolioOut,
)
from ..clock import now_ist, today_ist
from ..models.entity import LegalEntity
from ..services import document as docsvc
from ..services import fund as svc
from ..services import fy
from ..services.fund_perf import fund_performance
from ..services.fund_perf import performance_series as perf_series

router = APIRouter(tags=["fund"])


# --- fund profile (one per entity) ---
@router.post("/entities/{entity_id}/fund", response_model=FundOut, status_code=201)
def create_fund(
    body: FundIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    if db.query(Fund).filter_by(entity_id=ctx.entity.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Fund already exists for this entity")
    f = Fund(entity_id=ctx.entity.id, created_by=user.id, **body.model_dump())
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


@router.get("/entities/{entity_id}/fund", response_model=FundOut)
def get_fund(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    f = db.query(Fund).filter_by(entity_id=ctx.entity.id).first()
    if f is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No fund for this entity")
    return f


# --- fund construction / forecast ---
@router.get("/funds/{fund_id}/plan")
def get_plan(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.compute_plan(db, ctx.fund)


@router.put("/funds/{fund_id}/plan")
def save_plan(
    body: FundPlanIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    svc.upsert_plan(db, ctx.fund, body.model_dump())
    return svc.compute_plan(db, ctx.fund)


# --- LP-fundraising CRM (raising the fund from prospective LPs) ---
def _get_prospect(db: Session, fund_id: str, prospect_id: str) -> LPProspect:
    p = db.get(LPProspect, prospect_id)
    if p is None or p.fund_id != fund_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Prospect not found")
    return p


@router.get("/funds/{fund_id}/fundraise")
def fundraise(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.fundraise_summary(db, ctx.fund)


@router.post("/funds/{fund_id}/prospects", status_code=201)
def add_prospect(
    body: LPProspectIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    svc.add_prospect(db, ctx.fund, body.model_dump())
    return svc.fundraise_summary(db, ctx.fund)


@router.post("/funds/{fund_id}/prospects/{prospect_id}/stage")
def set_prospect_stage(
    prospect_id: str,
    body: LPProspectStageIn,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    p = _get_prospect(db, ctx.fund.id, prospect_id)
    svc.set_prospect_stage(db, p, body.stage)
    return svc.fundraise_summary(db, ctx.fund)


@router.post("/funds/{fund_id}/prospects/{prospect_id}/convert", response_model=LPOut, status_code=201)
def convert_prospect(
    prospect_id: str,
    body: LPProspectConvertIn,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    p = _get_prospect(db, ctx.fund.id, prospect_id)
    return svc.convert_prospect_to_lp(db, p, body.commitment)


# --- LP-prospect CRM: activity timeline, strength, follow-ups (FR-J-16) ---
def _prospect_crm(db: Session, prospect: LPProspect) -> dict:
    acts = (
        db.query(LPProspectActivity)
        .filter_by(prospect_id=prospect.id)
        .order_by(LPProspectActivity.occurred_on.desc(), LPProspectActivity.created_at.desc())
        .all()
    )
    return {
        "strength": _rel_strength(acts, today_ist()),
        "next_followup_on": prospect.next_followup_on,
        "activities": [
            {"id": a.id, "kind": a.kind, "body": a.body, "occurred_on": a.occurred_on}
            for a in acts
        ],
    }


@router.get("/funds/{fund_id}/prospects/{prospect_id}/crm")
def prospect_crm(
    prospect_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    return _prospect_crm(db, _get_prospect(db, ctx.fund.id, prospect_id))


@router.post("/funds/{fund_id}/prospects/{prospect_id}/activities", status_code=201)
def add_prospect_activity(
    prospect_id: str,
    body: LPProspectActivityIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    p = _get_prospect(db, ctx.fund.id, prospect_id)
    db.add(
        LPProspectActivity(
            prospect_id=p.id,
            fund_id=ctx.fund.id,
            kind=body.kind,
            body=body.body,
            occurred_on=body.occurred_on or today_ist(),
            created_by=user.id,
        )
    )
    db.commit()
    return _prospect_crm(db, p)


@router.put("/funds/{fund_id}/prospects/{prospect_id}/followup")
def set_prospect_followup(
    prospect_id: str,
    body: DealFollowupIn,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    p = _get_prospect(db, ctx.fund.id, prospect_id)
    p.next_followup_on = body.on
    db.commit()
    return svc.fundraise_summary(db, ctx.fund)


# --- LPs ---
@router.post("/funds/{fund_id}/lps", response_model=LPOut, status_code=201)
def add_lp(body: LPIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    lp = LP(fund_id=ctx.fund.id, **body.model_dump())
    db.add(lp)
    db.commit()
    db.refresh(lp)
    return lp


@router.get("/funds/{fund_id}/lps", response_model=list[LPOut])
def list_lps(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return db.query(LP).filter_by(fund_id=ctx.fund.id).all()


# --- capital calls / drawdowns ---
@router.post("/funds/{fund_id}/capital-calls", response_model=CapitalCallOut, status_code=201)
def create_call(
    body: CapitalCallIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    return svc.create_capital_call(db, ctx.fund, body.pct, body.purpose, body.due_date)


@router.get("/funds/{fund_id}/capital-calls", response_model=list[CapitalCallOut])
def list_calls(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return (
        db.query(CapitalCall).filter_by(fund_id=ctx.fund.id).order_by(CapitalCall.call_no).all()
    )


@router.post("/funds/{fund_id}/drawdown-notices/{notice_id}/pay", response_model=DrawdownNoticeOut)
def pay_notice(
    notice_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    notice = db.get(DrawdownNotice, notice_id)
    if notice is None or notice.fund_id != ctx.fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Drawdown notice not found")
    return svc.mark_paid(db, notice)


# --- distributions ---
@router.post("/funds/{fund_id}/distributions", response_model=DistributionOut, status_code=201)
def distribute(
    body: DistributionIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    return svc.record_distribution(db, ctx.fund, body.gross_amount, body.kind, body.date)


@router.get("/funds/{fund_id}/distributions", response_model=list[DistributionOut])
def list_distributions(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return (
        db.query(Distribution).filter_by(fund_id=ctx.fund.id).order_by(Distribution.dist_no).all()
    )


# --- capital accounts (projection) ---
@router.get("/funds/{fund_id}/capital-accounts")
def capital_accounts(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.capital_accounts(db, ctx.fund)


_COMPANY_TYPES = (EntityType.PVT_LTD, EntityType.LLP, EntityType.OPC)


def _accessible_company(db: Session, user: User, entity_id: str) -> LegalEntity:
    """The company entity `entity_id`, but only if the caller is a member of its
    workspace — a fund can only link to companies its GP can already see."""
    ent = db.get(LegalEntity, entity_id)
    if ent is None or ent.type not in _COMPANY_TYPES:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Company not found")
    member = (
        db.query(Membership).filter_by(user_id=user.id, tenant_id=ent.tenant_id).first()
    )
    if member is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "No access to that company's workspace")
    return ent


# --- portfolio ---
@router.post("/funds/{fund_id}/portfolio", response_model=PortfolioOut, status_code=201)
def add_investment(
    body: PortfolioIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    data = body.model_dump()
    if data.get("company_entity_id"):
        # linking to a Paper company keeps the name in sync with the source
        ent = _accessible_company(db, user, data["company_entity_id"])
        data["company_name"] = ent.name
    inv = PortfolioInvestment(fund_id=ctx.fund.id, **data)
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.get("/funds/{fund_id}/portfolio", response_model=list[PortfolioOut])
def list_portfolio(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return db.query(PortfolioInvestment).filter_by(fund_id=ctx.fund.id).all()


@router.get("/funds/{fund_id}/linkable-companies")
def linkable_companies(
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Companies in workspaces the GP belongs to — candidates to link a holding
    to (so the fund can reuse the company's own data)."""
    rows = (
        db.query(LegalEntity)
        .join(Membership, Membership.tenant_id == LegalEntity.tenant_id)
        .filter(Membership.user_id == user.id, LegalEntity.type.in_(_COMPANY_TYPES))
        .all()
    )
    return [{"id": e.id, "name": e.name} for e in rows]


@router.post("/funds/{fund_id}/portfolio/{investment_id}/pull-financials")
def pull_financials(
    investment_id: str,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pull the linked company's latest self-reported financials (revenue / cash
    / burn from its Finance module) in as a portfolio KPI period — no separate
    KPI request round-trip. Requires the holding to be linked and the GP to have
    access to that company's workspace."""
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    if not inv.company_entity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Holding is not linked to a company")
    _accessible_company(db, user, inv.company_entity_id)
    snap = (
        db.query(FinancialSnapshot)
        .filter_by(entity_id=inv.company_entity_id)
        .order_by(FinancialSnapshot.period.desc())
        .first()
    )
    if snap is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "The linked company has no financial snapshots yet"
        )
    label = snap.period.strftime("%b %Y")
    existing = (
        db.query(PortfolioKPI)
        .filter_by(investment_id=inv.id, period_label=label)
        .first()
    )
    values = {
        "revenue": snap.revenue,
        "cash": snap.cash_balance,
        "monthly_burn": snap.monthly_burn,
    }
    if existing:
        for k, v in values.items():
            setattr(existing, k, v)
        db.commit()
        db.refresh(existing)
        return svc._kpi_view(existing)
    kpi = svc.add_kpi(
        db, inv, {"period_label": label, "as_of": snap.period, "note": "Pulled from company Finance", **values}
    )
    return svc._kpi_view(kpi)


@router.get("/funds/{fund_id}/soi")
def schedule_of_investments(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    """Schedule of Investments (FR-J-11): cost, mark, MOIC, %NAV per holding."""
    return svc.schedule_of_investments(db, ctx.fund)


@router.post("/funds/{fund_id}/soi/report", response_model=DocumentOut, status_code=201)
def soi_report(
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    soi = svc.schedule_of_investments(db, ctx.fund)
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    lines = [
        f"  {h['company_name']} ({h['instrument']}): cost ₹{h['cost']} · value ₹{h['current_value']}"
        f" · MOIC {h['moic'] or '—'} · {h['pct_of_nav']}% of NAV"
        for h in soi["holdings"]
    ] or ["  No portfolio holdings recorded."]
    t = soi["totals"]
    doc = docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="soi_statement",
        data={
            "fund": entity.name if entity else "",
            "date": today_ist().isoformat(),
            "count": t["count"],
            "holdings": "\n".join(lines),
            "total_cost": t["cost"],
            "total_value": t["current_value"],
            "total_gain": t["unrealized_gain"],
            "moic": t["moic"] or "—",
        },
        user_id=user.id,
        title=f"Schedule of Investments — {today_ist().isoformat()}",
        subject_type="soi",
        subject_id=ctx.fund.id,
    )
    return docsvc.document_view(db, doc)


# --- SEBI independent portfolio valuation ---
@router.put("/funds/{fund_id}/valuation-policy", response_model=FundOut)
def set_valuation_policy(
    body: FundValuationPolicyIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    return svc.set_valuation_policy(db, ctx.fund, body.valuer_name, body.valuation_frequency_months)


@router.get("/funds/{fund_id}/valuations")
def valuation_summary(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.valuation_summary(db, ctx.fund)


@router.post("/funds/{fund_id}/portfolio/{investment_id}/valuations", status_code=201)
def record_valuation(
    investment_id: str,
    body: PortfolioValuationIn,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    svc.record_valuation(db, inv, body.model_dump())
    return svc.valuation_history(db, inv)


@router.get("/funds/{fund_id}/portfolio/{investment_id}/valuations")
def list_valuations(
    investment_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    inv = _get_investment(db, ctx.fund.id, investment_id)
    return svc.valuation_history(db, inv)


@router.post("/funds/{fund_id}/valuations/report", response_model=DocumentOut, status_code=201)
def valuation_report(
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    summary = svc.valuation_summary(db, ctx.fund)
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    lines = []
    for h in summary["holdings"]:
        lat = h["latest"]
        if lat:
            lines.append(
                f"  {h['company_name']}: ₹{lat['value']} ({lat['methodology_label']}) "
                f"by {lat['valuer'] or 'n/a'} as of {lat['as_of']}"
                f"{' [STALE]' if h['stale'] else ''}"
            )
        else:
            lines.append(f"  {h['company_name']}: not yet valued")
    t = summary["totals"]
    doc = docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="fund_valuation",
        data={
            "fund": entity.name if entity else "",
            "date": today_ist().isoformat(),
            "valuer": ctx.fund.valuer_name or "(not appointed)",
            "frequency": str(ctx.fund.valuation_frequency_months),
            "holdings": "\n".join(lines) or "  No portfolio holdings.",
            "valued": t["valued"],
            "total": t["holdings"],
            "independent": t["independent"],
            "stale": t["stale"],
        },
        user_id=user.id,
        title=f"Portfolio Valuation Report — {today_ist().isoformat()}",
        subject_type="fund_valuation",
        subject_id=ctx.fund.id,
    )
    return docsvc.document_view(db, doc)


# --- company tear sheet (one-pager document) ---
@router.post(
    "/funds/{fund_id}/portfolio/{investment_id}/tear-sheet",
    response_model=DocumentOut,
    status_code=201,
)
def tear_sheet(
    investment_id: str,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """One-pager for a portfolio company: investment summary, value & MOIC,
    latest valuation, KPI trend and active signals — composed from the
    monitoring/valuation/signals services."""
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    inr = svc._inr  # lakh/crore formatting, consistent with signals

    cost = Decimal(inv.amount)
    fair = Decimal(inv.current_value) if inv.current_value is not None else cost
    moic = f"{(fair / cost).quantize(Decimal('0.01'))}×" if cost > 0 else "—"

    vals = svc.valuation_history(db, inv)
    if vals:
        v = vals[0]
        valuation = (
            f"{inr(v['value'])} ({v['methodology_label']}) by {v['valuer'] or 'n/a'}"
            f"{' [independent]' if v['is_independent'] else ''} as of {v['as_of']}"
        )
    else:
        valuation = "none recorded — fund's own mark" if inv.current_value else "none recorded"

    def _kpi_line(k: dict) -> str:
        runway = f"{k['runway_months']} mo" if k["runway_months"] is not None else "—"
        return (
            f"  {k['period_label']} ({k['as_of']}): "
            f"revenue {inr(k['revenue']) if k['revenue'] else '—'}"
            f" · cash {inr(k['cash']) if k['cash'] else '—'}"
            f" · burn {inr(k['monthly_burn']) if k['monthly_burn'] else '—'}"
            f" · HC {k['headcount'] if k['headcount'] is not None else '—'}"
            f" · runway {runway}"
        )

    # kpi_history is ascending by as_of; show the latest 4, newest first
    kpi_lines = [
        _kpi_line(k) for k in list(reversed(svc.kpi_history(db, inv)))[:4]
    ] or ["  No KPI periods reported."]

    sig = next(
        (c for c in svc.portfolio_signals(db, ctx.fund)["companies"]
         if c["investment_id"] == inv.id),
        None,
    )
    sig_lines = (
        [f"  [{s['severity'].upper()}] {s['message']}" for s in sig["signals"]]
        if sig
        else ["  None — healthy on the latest reported data."]
    )

    doc = docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="tear_sheet",
        data={
            "company": inv.company_name,
            "fund": entity.name if entity else "",
            "date": today_ist().isoformat(),
            "instrument": inv.instrument,
            "invested": inr(cost),
            "ownership": str(inv.ownership_pct),
            "invested_on": str(inv.invested_on or "—"),
            "contact": inv.contact_email or "—",
            "cost": inr(cost),
            "fair_value": inr(fair),
            "moic": moic,
            "gain": inr(fair - cost),
            "valuation": valuation,
            "kpis": "\n".join(kpi_lines),
            "signals": "\n".join(sig_lines),
        },
        user_id=user.id,
        title=f"Tear Sheet — {inv.company_name} — {today_ist().isoformat()}",
        subject_type="tear_sheet",
        subject_id=inv.id,
    )
    return docsvc.document_view(db, doc)


# --- quarterly LP report pack ---
@router.get("/funds/{fund_id}/lp-report/preview")
def lp_report_preview(
    period_label: str | None = None,
    period_start: datetime.date | None = None,
    period_end: datetime.date | None = None,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    """Structured report data for the on-screen magazine view; defaults to the
    last completed quarter when no period is given."""
    if not (period_label and period_start and period_end):
        period_label, period_start, period_end = svc.default_report_period(today_ist())
    if period_end < period_start:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "period_end is before period_start")
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    return svc.lp_report_data(
        db, ctx.fund, entity.name if entity else "", period_label, period_start, period_end
    )


@router.post("/funds/{fund_id}/lp-report", response_model=DocumentOut, status_code=201)
def lp_report(
    body: LPReportIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Quarterly report to LPs: fund snapshot, since-inception performance,
    the period's capital calls and distributions, the Schedule of Investments
    and valuation status. Surfaces automatically in every LP's portal."""
    require_write(ctx.role)
    if body.period_end < body.period_start:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "period_end is before period_start"
        )
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    inr = svc._inr

    caps = svc.capital_accounts(db, ctx.fund)["totals"]
    perf = fund_performance(db, ctx.fund)
    activity = svc.period_activity(db, ctx.fund, body.period_start, body.period_end)
    soi = svc.schedule_of_investments(db, ctx.fund)
    vals = svc.valuation_summary(db, ctx.fund)["totals"]

    act_lines = [
        f"  Capital call #{c['call_no']} ({c['date']}): {inr(c['amount'])}"
        + (f" — {c['purpose']}" if c["purpose"] else "")
        for c in activity["capital_calls"]
    ] + [
        f"  Distribution #{d['dist_no']} ({d['date']}): {inr(d['gross_amount'])} gross"
        f" ({d['kind']}, carry {inr(d['carry_amount'])})"
        for d in activity["distributions"]
    ]
    holdings_lines = [
        f"  {h['company_name']}: cost {inr(h['cost'])}"
        f" · fair value {inr(h['current_value'])}"
        f" · MOIC {h['moic'] or '—'}× · {h['pct_of_nav']}% of NAV"
        for h in soi["holdings"]
    ]
    doc = docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="lp_report",
        data={
            "fund": entity.name if entity else "",
            "category": ctx.fund.sebi_category.value,
            "period": body.period_label,
            "period_start": body.period_start.isoformat(),
            "period_end": body.period_end.isoformat(),
            "date": today_ist().isoformat(),
            "committed": inr(caps["committed"]),
            "drawn": inr(caps["drawn"]),
            "uncalled": inr(caps["remaining"]),
            "distributed": inr(caps["distributed"]),
            "nav": inr(perf["nav"]),
            "nav_per_unit": perf["nav_per_unit"] or "—",
            "dpi": perf["dpi"] or "—",
            "rvpi": perf["rvpi"] or "—",
            "tvpi": perf["tvpi"] or "—",
            "xirr": f"{perf['xirr_pct']}%" if perf["xirr_pct"] is not None else "—",
            "activity": "\n".join(act_lines)
            or "  No capital calls or distributions this period.",
            "holdings": "\n".join(holdings_lines) or "  No portfolio holdings.",
            "total_cost": inr(soi["totals"]["cost"]),
            "total_value": inr(soi["totals"]["current_value"]),
            "total_moic": f"{soi['totals']['moic'] or '—'}×",
            "valuation_status": (
                f"{vals['valued']} of {vals['holdings']} holdings valued"
                f" · {vals['independent']} independently · {vals['stale']} stale vs policy"
            ),
        },
        user_id=user.id,
        title=f"LP Report — {body.period_label}",
        subject_type="lp_report",
        subject_id=ctx.fund.id,
    )
    return docsvc.document_view(db, doc)


# --- portfolio signals (risk early-warning) ---
@router.get("/funds/{fund_id}/signals")
def portfolio_signals(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.portfolio_signals(db, ctx.fund)


# --- KPI reporting requests (investee self-service) ---
@router.get("/funds/{fund_id}/kpi-requests")
def list_kpi_requests(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    svc.ensure_scheduled_requests(db, ctx.fund)  # materialise due scheduled requests
    return svc.list_kpi_requests(db, ctx.fund)


# --- recurring request schedules ---
@router.get("/funds/{fund_id}/kpi-schedules")
def list_kpi_schedules(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.list_kpi_schedules(db, ctx.fund)


@router.put("/funds/{fund_id}/portfolio/{investment_id}/kpi-schedule")
def upsert_kpi_schedule(
    investment_id: str,
    body: KPIScheduleIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    return svc.upsert_kpi_schedule(db, inv, body.model_dump(), user.id)


@router.delete("/funds/{fund_id}/portfolio/{investment_id}/kpi-schedule", status_code=204)
def delete_kpi_schedule(
    investment_id: str,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    svc.delete_kpi_schedule(db, ctx.fund, investment_id)


# --- no-login KPI submission via secret link token (public, unauthenticated) ---
def _request_by_token(db: Session, token: str):
    from ..models.fund import KPIRequest

    req = (
        db.query(KPIRequest).filter(KPIRequest.token == token).first() if token else None
    )
    if req is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "KPI request not found")
    return req


@router.get("/public/kpi-requests/{token}")
def public_kpi_request(token: str, db: Session = Depends(get_db)):
    req = _request_by_token(db, token)
    inv = db.get(PortfolioInvestment, req.investment_id)
    return {
        "company_name": inv.company_name if inv else None,
        "period_label": req.period_label,
        "as_of": req.as_of,
        "due_date": req.due_date,
        "status": req.status.value,
    }


@router.post("/public/kpi-requests/{token}/submit")
def public_kpi_submit(token: str, body: KPIRequestSubmitIn, db: Session = Depends(get_db)):
    req = _request_by_token(db, token)
    return svc.submit_request_values(db, req, body.model_dump())


@router.post("/funds/{fund_id}/portfolio/{investment_id}/kpi-requests", status_code=201)
def create_kpi_request(
    investment_id: str,
    body: KPIRequestIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    svc.create_kpi_request(db, inv, body.model_dump(), user.id)
    return svc.list_kpi_requests(db, ctx.fund)


def _get_kpi_request(db: Session, fund_id: str, request_id: str):
    from ..models.fund import KPIRequest

    req = db.get(KPIRequest, request_id)
    if req is None or req.fund_id != fund_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "KPI request not found")
    return req


@router.post("/funds/{fund_id}/kpi-requests/{request_id}/accept")
def accept_kpi_request(
    request_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    req = _get_kpi_request(db, ctx.fund.id, request_id)
    svc.accept_kpi_request(db, req)
    return svc.list_kpi_requests(db, ctx.fund)


@router.post("/funds/{fund_id}/kpi-requests/{request_id}/reopen")
def reopen_kpi_request(
    request_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    req = _get_kpi_request(db, ctx.fund.id, request_id)
    svc.reopen_kpi_request(db, req)
    return svc.list_kpi_requests(db, ctx.fund)


# --- portfolio-company monitoring (KPIs) ---
def _get_investment(db: Session, fund_id: str, investment_id: str) -> PortfolioInvestment:
    inv = db.get(PortfolioInvestment, investment_id)
    if inv is None or inv.fund_id != fund_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investment not found")
    return inv


@router.get("/funds/{fund_id}/portfolio-monitoring")
def portfolio_monitoring(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.portfolio_monitoring(db, ctx.fund)


# --- custom KPI definitions + ESG presets (FR-J-23) ---
@router.get("/funds/{fund_id}/kpi-definitions")
def list_kpi_definitions(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return {
        "definitions": svc.list_kpi_definitions(db, ctx.fund),
        "presets": svc.ESG_KPI_PRESETS,
    }


@router.post("/funds/{fund_id}/kpi-definitions", status_code=201)
def create_kpi_definition(
    body: KPIDefinitionIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    d = svc.create_kpi_definition(db, ctx.fund, body.model_dump(), user.id)
    return svc._definition_view(d)


@router.delete("/funds/{fund_id}/kpi-definitions/{definition_id}", status_code=204)
def delete_kpi_definition(
    definition_id: str,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    svc.delete_kpi_definition(db, ctx.fund, definition_id)


# --- metric alert rules: fund-defined thresholds (FR-J-20 extended) ---
@router.get("/funds/{fund_id}/alert-rules")
def list_alert_rules(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.list_alert_rules(db, ctx.fund)


@router.post("/funds/{fund_id}/alert-rules", status_code=201)
def create_alert_rule(
    body: MetricAlertRuleIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.create_alert_rule(db, ctx.fund, body.model_dump(), user.id)


@router.delete("/funds/{fund_id}/alert-rules/{rule_id}", status_code=204)
def delete_alert_rule(
    rule_id: str,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    svc.delete_alert_rule(db, ctx.fund, rule_id)


# --- follow-on investment rounds (Rundit-style per-round history) ---
@router.get("/funds/{fund_id}/portfolio/{investment_id}/rounds")
def list_investment_rounds(
    investment_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    inv = _get_investment(db, ctx.fund.id, investment_id)
    return svc.investment_rounds(db, inv)


@router.post("/funds/{fund_id}/portfolio/{investment_id}/rounds", status_code=201)
def add_investment_round(
    investment_id: str,
    body: InvestmentRoundIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    svc.add_investment_round(db, inv, body.model_dump(), user.id)
    return svc.investment_rounds(db, inv)


# --- fund expense ledger ---
@router.get("/funds/{fund_id}/expenses")
def list_fund_expenses(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.list_fund_expenses(db, ctx.fund)


@router.post("/funds/{fund_id}/expenses", status_code=201)
def add_fund_expense(
    body: FundExpenseIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    svc.add_fund_expense(db, ctx.fund, body.model_dump(), user.id)
    return svc.list_fund_expenses(db, ctx.fund)


@router.delete("/funds/{fund_id}/expenses/{expense_id}", status_code=204)
def delete_fund_expense(
    expense_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    svc.delete_fund_expense(db, ctx.fund, expense_id)


# --- internal team notes on portfolio companies ---
@router.get("/funds/{fund_id}/portfolio/{investment_id}/notes")
def list_company_notes(
    investment_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    inv = _get_investment(db, ctx.fund.id, investment_id)
    return svc.list_company_notes(db, inv)


@router.post("/funds/{fund_id}/portfolio/{investment_id}/notes", status_code=201)
def add_company_note(
    investment_id: str,
    body: CompanyNoteIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    svc.add_company_note(db, inv, body.body, user.id)
    return svc.list_company_notes(db, inv)


@router.delete("/funds/{fund_id}/portfolio/{investment_id}/notes/{note_id}", status_code=204)
def delete_company_note(
    investment_id: str,
    note_id: str,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    svc.delete_company_note(db, inv, note_id)


# --- CSV exports (Rundit-style data out) ---
def _csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    w.writerows(rows)
    return Response(
        content=out.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/funds/{fund_id}/export/holdings")
def export_holdings(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    soi = svc.schedule_of_investments(db, ctx.fund)
    return _csv_response(
        "fund_holdings.csv",
        ["company_name", "instrument", "invested_on", "cost", "current_value",
         "marked", "ownership_pct", "moic", "unrealized_gain", "pct_of_nav"],
        [[h["company_name"], h["instrument"], h["invested_on"], h["cost"],
          h["current_value"], h["marked"], h["ownership_pct"], h["moic"],
          h["unrealized_gain"], h["pct_of_nav"]] for h in soi["holdings"]],
    )


@router.get("/funds/{fund_id}/export/capital-accounts")
def export_capital_accounts(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    accounts = svc.capital_accounts(db, ctx.fund)["accounts"]
    return _csv_response(
        "capital_accounts.csv",
        ["lp_name", "committed", "drawn", "remaining", "distributed", "fees_charged", "units"],
        [[a["lp_name"], a["committed"], a["drawn"], a["remaining"],
          a["distributed"], a["fees_charged"], a["units"]] for a in accounts],
    )


@router.get("/funds/{fund_id}/export/kpis")
def export_kpis(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    import json

    rows = []
    for inv in db.query(PortfolioInvestment).filter_by(fund_id=ctx.fund.id):
        for k in (
            db.query(PortfolioKPI)
            .filter_by(investment_id=inv.id)
            .order_by(PortfolioKPI.as_of)
        ):
            rows.append([
                inv.company_name, k.period_label, k.as_of, k.revenue, k.cash,
                k.monthly_burn, k.headcount, json.dumps(k.custom) if k.custom else "",
            ])
    return _csv_response(
        "portfolio_kpis.csv",
        ["company_name", "period_label", "as_of", "revenue", "cash",
         "monthly_burn", "headcount", "custom"],
        rows,
    )


# --- DDQ answer bank: due-diligence questionnaire responses ---
@router.get("/funds/{fund_id}/ddq")
def list_ddq(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return {"entries": svc.list_ddq(db, ctx.fund), "presets": svc.DDQ_PRESETS}


@router.post("/funds/{fund_id}/ddq", status_code=201)
def create_ddq_entry(
    body: DDQEntryIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.create_ddq_entry(db, ctx.fund, body.model_dump(), user.id)


@router.put("/funds/{fund_id}/ddq/{entry_id}")
def update_ddq_entry(
    entry_id: str,
    body: DDQEntryUpdateIn,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.update_ddq_entry(db, ctx.fund, entry_id, body.model_dump(exclude_unset=True))


@router.delete("/funds/{fund_id}/ddq/{entry_id}", status_code=204)
def delete_ddq_entry(
    entry_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    svc.delete_ddq_entry(db, ctx.fund, entry_id)


@router.post("/funds/{fund_id}/ddq/report", response_model=DocumentOut, status_code=201)
def ddq_report(
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    doc = docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="ddq",
        data={
            "fund": entity.name if entity else "",
            "category": ctx.fund.sebi_category.value,
            "date": today_ist().isoformat(),
            "sections": svc.ddq_sections(db, ctx.fund),
        },
        user_id=user.id,
        title="DDQ Responses",
        subject_type="ddq",
        subject_id=ctx.fund.id,
    )
    return docsvc.document_view(db, doc)


# --- internal benchmarking: portfolio medians (FR-J-24) ---
@router.get("/funds/{fund_id}/benchmarks")
def portfolio_benchmarks(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.portfolio_benchmarks(db, ctx.fund)


@router.post("/funds/{fund_id}/portfolio/{investment_id}/kpis", status_code=201)
def add_kpi(
    investment_id: str,
    body: PortfolioKPIIn,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inv = _get_investment(db, ctx.fund.id, investment_id)
    svc.add_kpi(db, inv, body.model_dump())
    return svc.kpi_history(db, inv)


@router.get("/funds/{fund_id}/portfolio/{investment_id}/kpis")
def list_kpis(
    investment_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    inv = _get_investment(db, ctx.fund.id, investment_id)
    return svc.kpi_history(db, inv)


@router.put("/funds/{fund_id}/portfolio/{investment_id}/mark", response_model=PortfolioOut)
def mark_investment(
    investment_id: str,
    body: PortfolioMarkIn,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    inv = db.get(PortfolioInvestment, investment_id)
    if inv is None or inv.fund_id != ctx.fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investment not found")
    inv.current_value = body.current_value
    inv.marked_on = body.marked_on or today_ist()
    db.commit()
    db.refresh(inv)
    return inv


# --- deal pipeline (GP-side CRM) ---
@router.post("/funds/{fund_id}/deals", response_model=DealOut, status_code=201)
def create_deal(body: DealIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    d = Deal(fund_id=ctx.fund.id, **body.model_dump())
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


@router.get("/funds/{fund_id}/deals", response_model=list[DealOut])
def list_deals(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return db.query(Deal).filter_by(fund_id=ctx.fund.id).order_by(Deal.created_at.desc()).all()


@router.post("/deals/{deal_id}/stage", response_model=DealOut)
def set_deal_stage(
    body: DealStageIn, ctx: DealCtx = Depends(deal_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ctx.deal.stage = body.stage
    ctx.deal.stage_changed_at = now_ist()
    db.commit()
    db.refresh(ctx.deal)
    return ctx.deal


@router.post("/deals/{deal_id}/invest", response_model=DealOut)
def invest_deal(
    body: DealInvestIn, ctx: DealCtx = Depends(deal_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    deal = ctx.deal
    if deal.investment_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Deal is already invested")
    inv = PortfolioInvestment(
        fund_id=deal.fund_id,
        company_name=deal.company_name,
        amount=deal.amount,
        ownership_pct=body.ownership_pct,
        invested_on=body.invested_on or today_ist(),
    )
    db.add(inv)
    db.flush()
    deal.investment_id = inv.id
    deal.stage = DealStage.INVESTED
    db.commit()
    db.refresh(deal)
    return deal


# --- deal CRM: contacts + activity timeline ---
def _rel_strength(acts: list[DealActivity], today: datetime.date) -> int:
    """0-100 heuristic from logged touches (4Degrees-style, activity-driven):
    frequency (15/touch up to 60) + recency (40 fading to 0 over 6 months)."""
    if not acts:
        return 0
    freq = min(60, len(acts) * 15)
    days = max(0, (today - max(a.occurred_on for a in acts)).days)
    recency = max(0, round(40 * (1 - days / 183)))
    return min(100, freq + recency)


def _deal_crm(db: Session, deal_id: str) -> dict:
    contacts = db.query(DealContact).filter_by(deal_id=deal_id).order_by(DealContact.created_at).all()
    acts = (
        db.query(DealActivity)
        .filter_by(deal_id=deal_id)
        .order_by(DealActivity.occurred_on.desc(), DealActivity.created_at.desc())
        .all()
    )
    today = today_ist()
    return {
        "strength": _rel_strength(acts, today),
        "contacts": [
            {
                "id": c.id,
                "name": c.name,
                "role": c.role,
                "email": c.email,
                "note": c.note,
                "strength": _rel_strength([a for a in acts if a.contact_id == c.id], today),
            }
            for c in contacts
        ],
        "activities": [
            {
                "id": a.id,
                "kind": a.kind,
                "body": a.body,
                "occurred_on": a.occurred_on,
                "contact_id": a.contact_id,
            }
            for a in acts
        ],
    }


@router.get("/deals/{deal_id}/crm")
def deal_crm(ctx: DealCtx = Depends(deal_ctx), db: Session = Depends(get_db)):
    return _deal_crm(db, ctx.deal.id)


@router.post("/deals/{deal_id}/contacts", status_code=201)
def add_deal_contact(
    body: DealContactIn, ctx: DealCtx = Depends(deal_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    db.add(DealContact(deal_id=ctx.deal.id, **body.model_dump()))
    db.commit()
    return _deal_crm(db, ctx.deal.id)


@router.post("/deals/{deal_id}/activities", status_code=201)
def add_deal_activity(
    body: DealActivityIn,
    ctx: DealCtx = Depends(deal_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    if body.contact_id is not None:
        contact = db.get(DealContact, body.contact_id)
        if contact is None or contact.deal_id != ctx.deal.id:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found on this deal")
    db.add(DealActivity(
        deal_id=ctx.deal.id,
        kind=body.kind,
        body=body.body,
        occurred_on=body.occurred_on or today_ist(),
        created_by=user.id,
        contact_id=body.contact_id,
    ))
    db.commit()
    return _deal_crm(db, ctx.deal.id)


# --- deal pipeline CSV import (onboarding an existing pipeline, FR-J-10) ---
DEALS_IMPORT_TEMPLATE = (
    "company_name,sector,stage,amount,source\n"
    "Acme Robotics,DeepTech,screening,15000000,IIT network\n"
    "BlueLeaf Foods,Consumer,sourced,8000000,\n"
)
_DEAL_STAGES = {s.value for s in DealStage}


@router.get("/funds/{fund_id}/deals/import-template")
def deals_import_template(ctx: FundCtx = Depends(fund_ctx)):
    return Response(
        content=DEALS_IMPORT_TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="deals-import.csv"'},
    )


@router.post("/funds/{fund_id}/deals/import")
def import_deals(
    body: DealsImportIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    """Validate a deals CSV (required: company_name; optional: sector, stage,
    amount, source); with apply=true, create the deals atomically."""
    require_write(ctx.role)
    reader = csv.DictReader(io.StringIO(body.csv))
    if not reader.fieldnames or "company_name" not in reader.fieldnames:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "CSV needs a company_name column")
    rows: list[dict] = []
    errors: list[str] = []
    for i, r in enumerate(reader, start=2):
        name = (r.get("company_name") or "").strip()
        if not name:
            errors.append(f"row {i}: company_name is required")
            continue
        stage = ((r.get("stage") or "").strip().lower()) or "sourced"
        if stage not in _DEAL_STAGES:
            errors.append(f"row {i}: unknown stage '{stage}' (use {sorted(_DEAL_STAGES)})")
            continue
        try:
            amount = Decimal((r.get("amount") or "").strip() or "0")
        except InvalidOperation:
            errors.append(f"row {i}: amount is not a number")
            continue
        if amount < 0:
            errors.append(f"row {i}: amount must not be negative")
            continue
        rows.append(
            {
                "company_name": name,
                "sector": (r.get("sector") or "").strip() or None,
                "stage": DealStage(stage),
                "amount": amount,
                "source": (r.get("source") or "").strip() or None,
            }
        )
    report = {"valid": not errors, "rows": len(rows), "errors": errors}
    if not body.apply:
        return report
    if errors:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"message": "CSV has errors — nothing was imported", "errors": errors},
        )
    for r in rows:
        db.add(Deal(fund_id=ctx.fund.id, **r))
    db.commit()
    return {**report, "applied": True, "imported": len(rows)}


# --- firm network directory: everyone the fund knows (FR-J-17) ---
@router.get("/funds/{fund_id}/network")
def firm_network(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    """One roster across deal contacts and LP prospects — "who do we know at X"
    — with relationship strength and last touch, deduped by email (else name).
    Derived entirely from the fund's own logged relationships."""
    today = today_ist()
    people: dict[str, dict] = {}

    def merge(key: str, name: str, role: str | None, email: str | None,
              link: str, strength: int, last_touch: datetime.date | None) -> None:
        e = people.setdefault(
            key,
            {"name": name, "role": role, "email": email, "links": [],
             "strength": 0, "last_touch": None},
        )
        if link not in e["links"]:
            e["links"].append(link)
        e["strength"] = max(e["strength"], strength)
        if last_touch and (e["last_touch"] is None or last_touch > e["last_touch"]):
            e["last_touch"] = last_touch
        if role and not e["role"]:
            e["role"] = role

    deals = {d.id: d for d in db.query(Deal).filter_by(fund_id=ctx.fund.id)}
    if deals:
        acts = db.query(DealActivity).filter(DealActivity.deal_id.in_(deals.keys())).all()
        by_contact: dict[str, list[DealActivity]] = {}
        for a in acts:
            if a.contact_id:
                by_contact.setdefault(a.contact_id, []).append(a)
        for c in db.query(DealContact).filter(DealContact.deal_id.in_(deals.keys())):
            mine = by_contact.get(c.id, [])
            merge(
                (c.email or f"name:{c.name.strip().lower()}"),
                c.name, c.role, c.email,
                f"deal: {deals[c.deal_id].company_name}",
                _rel_strength(mine, today),
                max((a.occurred_on for a in mine), default=None),
            )

    for p in db.query(LPProspect).filter_by(fund_id=ctx.fund.id):
        acts = db.query(LPProspectActivity).filter_by(prospect_id=p.id).all()
        merge(
            (p.email or f"name:{p.name.strip().lower()}"),
            p.name, p.firm, p.email,
            "LP fundraise",
            _rel_strength(acts, today),
            max((a.occurred_on for a in acts), default=None),
        )

    roster = sorted(
        people.values(),
        key=lambda e: (-e["strength"], e["name"].lower()),
    )
    return {"fund_id": ctx.fund.id, "count": len(roster), "people": roster}


@router.put("/deals/{deal_id}/followup", response_model=DealOut)
def set_deal_followup(
    body: DealFollowupIn, ctx: DealCtx = Depends(deal_ctx), db: Session = Depends(get_db)
):
    """Set (or clear with null) the deal's next follow-up date; overdue
    follow-ups surface in the pipeline and the entity Tasks hub."""
    require_write(ctx.role)
    ctx.deal.next_followup_on = body.on
    db.commit()
    db.refresh(ctx.deal)
    return ctx.deal


# --- management fees: charge accrual into capital accounts ---
@router.post("/funds/{fund_id}/fees/charge")
def charge_fees(
    as_of: datetime.date | None = None,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.charge_fees(db, ctx.fund, as_of or today_ist())


@router.get("/funds/{fund_id}/fees")
def list_fees(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return [
        {"id": f.id, "lp_id": f.lp_id, "amount": str(f.amount),
         "period_label": f.period_label, "charged_on": f.charged_on}
        for f in db.query(FeeCharge).filter_by(fund_id=ctx.fund.id).order_by(FeeCharge.charged_on)
    ]


# --- Form 64C / 64D (AIF income-distribution tax statements) ---
@router.post("/funds/{fund_id}/tax-statements", status_code=201)
def tax_statements(
    body: ComplianceGenerateIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    fy_end = body.financial_year_end
    fy_start = fy.fy_start(fy_end)
    fy_label = fy.fy_label(fy_end)
    entity = db.get(LegalEntity, ctx.fund.entity_id)

    dist_ids = {
        d.id
        for d in db.query(Distribution).filter_by(fund_id=ctx.fund.id)
        if d.date and fy_start <= d.date <= fy_end
    }
    per_lp: dict[str, Decimal] = {}
    for r in db.query(LPDistribution).filter_by(fund_id=ctx.fund.id):
        if r.distribution_id in dist_ids:
            per_lp[r.lp_id] = per_lp.get(r.lp_id, Decimal("0")) + Decimal(r.amount)

    acc = {a["lp_id"]: a for a in svc.capital_accounts(db, ctx.fund)["accounts"]}
    lps = {lp.id: lp for lp in db.query(LP).filter_by(fund_id=ctx.fund.id)}
    generated = 0
    rows = []
    for lp_id, amount in per_lp.items():
        lp = lps.get(lp_id)
        if lp is None:
            continue
        docsvc.create_document(
            db,
            entity_id=ctx.fund.entity_id,
            template_key="form_64c",
            data={
                "fund": entity.name if entity else "",
                "category": ctx.fund.sebi_category.value,
                "lp": lp.name,
                "fy": fy_label,
                "distributed": str(q(amount)),
                "units": acc[lp_id]["units"] if lp_id in acc else "0.00",
            },
            user_id=user.id,
            title=f"Form 64C — {lp.name} — {fy_label}",
            subject_type="form_64c",
            subject_id=lp.id,
        )
        rows.append(f"  {lp.name}: INR {q(amount)}")
        generated += 1

    total = sum(per_lp.values(), Decimal("0"))
    docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="form_64d",
        data={
            "fund": entity.name if entity else "",
            "category": ctx.fund.sebi_category.value,
            "fy": fy_label,
            "total_distributed": str(q(total)),
            "rows": "\n".join(rows) if rows else "  (no distributions this year)",
        },
        user_id=user.id,
        title=f"Form 64D — {fy_label}",
        subject_type="form_64d",
        subject_id=ctx.fund.id,
    )
    return {"form_64c": generated, "form_64d": 1, "total_distributed": str(q(total))}


# --- fund financial statements ---
@router.get("/funds/{fund_id}/financials")
def financials(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return svc.fund_financials(db, ctx.fund)


@router.post("/funds/{fund_id}/financials/report", response_model=DocumentOut, status_code=201)
def financials_report(
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    fin = svc.fund_financials(db, ctx.fund)
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    op, cf, bs, disc = fin["operations"], fin["cash_flow"], fin["balance_sheet"], fin["disclosures"]
    doc = docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="fund_financials",
        data={
            "fund": entity.name if entity else "",
            "date": str(fin["as_of"]),
            "unrealized": op["unrealized_appreciation"],
            "fees": op["management_fees"],
            "net_ops": op["net_increase_from_operations"],
            "contributions": cf["contributions"],
            "invested": disc["invested_at_cost"],
            "dist_lps": cf["distributions_to_lps"].lstrip("-"),
            "carry": cf["carry_paid"].lstrip("-"),
            "cash": bs["cash"],
            "investments_fv": bs["investments_at_fair_value"],
            "total_assets": bs["total_assets"],
            "liabilities": bs["liabilities"],
            "net_assets": bs["net_assets"],
            "committed": disc["committed"],
            "uncalled": disc["uncalled"],
        },
        user_id=user.id,
        title=f"Fund Financial Statements — {fin['as_of']}",
        subject_type="fund_financials",
        subject_id=ctx.fund.id,
    )
    return docsvc.document_view(db, doc)


# --- performance (DPI / RVPI / TVPI / XIRR, fees) ---
@router.get("/funds/{fund_id}/performance")
def performance(
    as_of: datetime.date | None = None,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    return fund_performance(db, ctx.fund, as_of)


@router.get("/funds/{fund_id}/performance-series")
def performance_series(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return perf_series(db, ctx.fund)


# --- LP capital-account statement (generated document, FR-J-7) ---
@router.post(
    "/funds/{fund_id}/lps/{lp_id}/statement", response_model=DocumentOut, status_code=201
)
def lp_statement(
    lp_id: str,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    lp = db.get(LP, lp_id)
    if lp is None or lp.fund_id != ctx.fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LP not found")
    acc = svc.capital_accounts(db, ctx.fund)
    mine = next((a for a in acc["accounts"] if a["lp_id"] == lp.id), None)
    perf = fund_performance(db, ctx.fund)
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    doc = docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="lp_statement",
        data={
            "fund": entity.name if entity else "",
            "lp": lp.name,
            "as_of": str(perf["as_of"]),
            "committed": mine["committed"] if mine else "0.00",
            "drawn": mine["drawn"] if mine else "0.00",
            "remaining": mine["remaining"] if mine else "0.00",
            "distributed": mine["distributed"] if mine else "0.00",
            "fees_charged": mine["fees_charged"] if mine else "0.00",
            "units": mine["units"] if mine else "0.00",
            "dpi": perf["dpi"] or "—",
            "tvpi": perf["tvpi"] or "—",
            "xirr": perf["xirr_pct"] if perf["xirr_pct"] is not None else "—",
            "nav": perf["nav"],
            "nav_per_unit": perf["nav_per_unit"] or "—",
        },
        user_id=user.id,
        title=f"LP Statement — {lp.name} — {perf['as_of']}",
        subject_type="lp_statement",
        subject_id=lp.id,
    )
    return docsvc.document_view(db, doc)

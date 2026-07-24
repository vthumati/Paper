import csv
import datetime
import io
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ...clock import today_ist
from ...db import get_db
from ...deps import (
    FundCtx,
    PageCtx,
    fund_ctx,
    get_current_user,
    page,
    require_write,
)
from ...models.entity import EntityType, LegalEntity
from ...models.finance import FinancialSnapshot
from ...models.fund import PortfolioInvestment, PortfolioKPI
from ...models.identity import Membership, User
from ...schemas import (
    CompanyNoteIn,
    DocumentOut,
    FundOut,
    FundValuationPolicyIn,
    KPIDefinitionIn,
    KPIRequestIn,
    KPIRequestSubmitIn,
    KPIScheduleIn,
    LPReportIn,
    MetricAlertRuleIn,
    PortfolioIn,
    PortfolioKPIIn,
    PortfolioMarkIn,
    PortfolioOut,
    PortfolioValuationIn,
)
from ...services import document as docsvc
from ...services import fund as svc
from ...services.fund_perf import fund_performance
from ._common import _get_investment

router = APIRouter(tags=["fund"])

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
    if not data.get("currency"):
        data["currency"] = ctx.fund.currency  # default to the fund's reporting currency
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
def list_portfolio(
    ctx: FundCtx = Depends(fund_ctx),
    p: PageCtx = Depends(page),
    db: Session = Depends(get_db),
):
    return (
        db.query(PortfolioInvestment)
        .filter_by(fund_id=ctx.fund.id)
        .order_by(PortfolioInvestment.created_at)
        .offset(p.offset)
        .limit(p.limit)
        .all()
    )


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
    from ...models.fund import KPIRequest

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
    from ...models.fund import KPIRequest

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
def _csv_safe(v):
    """Neutralise spreadsheet formula injection: a cell an attacker controls
    (e.g. a linked company's name) that starts with = + - @ (or a control
    char) is executed by Excel/Sheets on open — prefix it with a quote."""
    if isinstance(v, str) and v and v[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _csv_response(filename: str, header: list[str], rows: list[list]) -> Response:
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow(header)
    w.writerows([[_csv_safe(c) for c in row] for row in rows])
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

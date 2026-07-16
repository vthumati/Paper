import datetime

from fastapi import APIRouter, Depends, HTTPException, status
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
    DealStage,
    Distribution,
    DrawdownNotice,
    FeeCharge,
    Fund,
    LP,
    LPDistribution,
    PortfolioInvestment,
)
from ..services.money import q
from ..models.identity import User
from decimal import Decimal

from ..schemas import (
    CapitalCallIn,
    CapitalCallOut,
    ComplianceGenerateIn,
    DealIn,
    DealInvestIn,
    DealOut,
    DealStageIn,
    DistributionIn,
    DistributionOut,
    DocumentOut,
    DrawdownNoticeOut,
    FundIn,
    FundOut,
    LPIn,
    LPOut,
    PortfolioIn,
    PortfolioMarkIn,
    PortfolioOut,
)
from ..clock import today_ist
from ..models.entity import LegalEntity
from ..services import document as docsvc
from ..services import fund as svc
from ..services.fund_perf import fund_performance

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


# --- portfolio ---
@router.post("/funds/{fund_id}/portfolio", response_model=PortfolioOut, status_code=201)
def add_investment(
    body: PortfolioIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    inv = PortfolioInvestment(fund_id=ctx.fund.id, **body.model_dump())
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv


@router.get("/funds/{fund_id}/portfolio", response_model=list[PortfolioOut])
def list_portfolio(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return db.query(PortfolioInvestment).filter_by(fund_id=ctx.fund.id).all()


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
    fy_start = datetime.date(fy_end.year - 1, 4, 1)
    fy_label = f"FY{fy_end.year}"
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


# --- performance (DPI / RVPI / TVPI / XIRR, fees) ---
@router.get("/funds/{fund_id}/performance")
def performance(
    as_of: datetime.date | None = None,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    return fund_performance(db, ctx.fund, as_of)


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

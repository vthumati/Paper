import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...clock import today_ist
from ...db import get_db
from ...deps import FundCtx, fund_ctx, get_current_user, require_write
from ...models.entity import LegalEntity
from ...models.fund import (
    LP,
    CapitalCall,
    Distribution,
    DrawdownNotice,
    FeeCharge,
    LPDistribution,
)
from ...models.identity import User
from ...schemas import (
    AuditedFinancialsIn,
    BankDetailsIn,
    CapitalCallIn,
    CapitalCallOut,
    ComplianceGenerateIn,
    DistributionIn,
    DistributionOut,
    DocumentOut,
    DrawdownNoticeOut,
    FundExpenseIn,
    FundOut,
    InvestmentRoundIn,
    PayNoticeIn,
)
from ...services import document as docsvc
from ...services import fund as svc
from ...services import fy
from ...services.fund_perf import fund_performance
from ...services.fund_perf import performance_series as perf_series
from ...services.money import q
from ._common import _get_investment

router = APIRouter(tags=["fund"])


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
    notice_id: str,
    body: PayNoticeIn | None = None,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Verify receipt of a drawdown: mark paid, record the remittance reference
    (UTR) and who confirmed it."""
    require_write(ctx.role)
    notice = db.get(DrawdownNotice, notice_id)
    if notice is None or notice.fund_id != ctx.fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Drawdown notice not found")
    ref = body.payment_ref if body else None
    return svc.mark_paid(db, notice, payment_ref=ref, verified_by=user.id)


@router.post("/funds/{fund_id}/drawdown-notices/{notice_id}/notice", response_model=DocumentOut, status_code=201)
def drawdown_notice_doc(
    notice_id: str,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate the LP's drawdown-notice document (with remittance details)."""
    require_write(ctx.role)
    notice = db.get(DrawdownNotice, notice_id)
    if notice is None or notice.fund_id != ctx.fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Drawdown notice not found")
    doc = svc.generate_drawdown_notice(db, notice, user.id)
    return docsvc.document_view(db, doc)


@router.put("/funds/{fund_id}/bank", response_model=FundOut)
def set_fund_bank(
    body: BankDetailsIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    """Set the fund's collection/escrow bank account (shown on drawdown notices)."""
    require_write(ctx.role)
    ctx.fund.bank_name = body.bank_name
    ctx.fund.bank_account = body.bank_account
    ctx.fund.bank_ifsc = body.bank_ifsc
    db.commit()
    db.refresh(ctx.fund)
    return ctx.fund


@router.put("/funds/{fund_id}/lps/{lp_id}/bank")
def set_lp_bank(
    lp_id: str, body: BankDetailsIn, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    """Set an LP's bank details (for receiving distributions)."""
    require_write(ctx.role)
    lp = db.get(LP, lp_id)
    if lp is None or lp.fund_id != ctx.fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "LP not found")
    lp.bank_name = body.bank_name
    lp.bank_account = body.bank_account
    lp.bank_ifsc = body.bank_ifsc
    db.commit()
    return {"id": lp.id, "bank_name": lp.bank_name, "bank_account": lp.bank_account, "bank_ifsc": lp.bank_ifsc}


@router.post("/funds/{fund_id}/audited-financials", response_model=DocumentOut, status_code=201)
def audited_financials(
    body: AuditedFinancialsIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an audited-financials document LPs can download from the vault."""
    require_write(ctx.role)
    doc = svc.generate_audited_financials(db, ctx.fund, body.auditor_name, user.id)
    return docsvc.document_view(db, doc)


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

import csv
import datetime
import io
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ...clock import now_ist, today_ist
from ...db import get_db
from ...deps import (
    DealCtx,
    FundCtx,
    PageCtx,
    deal_ctx,
    fund_ctx,
    get_current_user,
    page,
    require_write,
)
from ...models.fund import (
    Deal,
    DealActivity,
    DealContact,
    DealStage,
    LPProspect,
    LPProspectActivity,
    PortfolioInvestment,
)
from ...models.identity import User
from ...schemas import (
    DealActivityIn,
    DealContactIn,
    DealFollowupIn,
    DealIn,
    DealInvestIn,
    DealOut,
    DealsImportIn,
    DealStageIn,
)
from ._common import _rel_strength

router = APIRouter(tags=["fund"])


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
def list_deals(
    ctx: FundCtx = Depends(fund_ctx),
    p: PageCtx = Depends(page),
    db: Session = Depends(get_db),
):
    return (
        db.query(Deal)
        .filter_by(fund_id=ctx.fund.id)
        .order_by(Deal.created_at.desc())
        .offset(p.offset)
        .limit(p.limit)
        .all()
    )


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

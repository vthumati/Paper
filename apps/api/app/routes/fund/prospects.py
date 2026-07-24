from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...clock import today_ist
from ...db import get_db
from ...deps import FundCtx, fund_ctx, get_current_user, require_write
from ...models.fund import LPProspect, LPProspectActivity
from ...models.identity import User
from ...schemas import (
    DealFollowupIn,
    LPOut,
    LPProspectActivityIn,
    LPProspectConvertIn,
    LPProspectIn,
    LPProspectStageIn,
)
from ...services import fund as svc
from ._common import _rel_strength

router = APIRouter(tags=["fund"])


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

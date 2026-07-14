
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import EntityCtx, RoundCtx, entity_ctx, get_current_user, require_write, round_ctx
from ..models.entity import LegalEntity
from ..models.identity import User
from ..models.round import Commitment, Round
from ..schemas import (
    DocumentOut,
    RoundCommitmentIn,
    RoundCommitmentOut,
    RoundCommitmentStatusIn,
    RoundIn,
    RoundOut,
)
from ..services import document as docsvc
from ..services import notification as notifsvc
from ..services import round as svc
from ..services.placement import check_offeree_limit

router = APIRouter(tags=["fundraising"])


@router.post("/entities/{entity_id}/rounds", response_model=RoundOut, status_code=201)
def create_round(
    body: RoundIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    rnd = Round(entity_id=ctx.entity.id, created_by=user.id, **body.model_dump())
    db.add(rnd)
    db.commit()
    db.refresh(rnd)
    return rnd


@router.get("/entities/{entity_id}/rounds", response_model=list[RoundOut])
def list_rounds(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(Round).filter_by(entity_id=ctx.entity.id).all()


@router.get("/rounds/{round_id}", response_model=RoundOut)
def get_round(ctx: RoundCtx = Depends(round_ctx)):
    return ctx.round


@router.post("/rounds/{round_id}/commitments", response_model=RoundCommitmentOut, status_code=201)
def add_commitment(
    body: RoundCommitmentIn, ctx: RoundCtx = Depends(round_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    check_offeree_limit(db, ctx.round.entity_id, body.investor_name, today_ist())
    c = Commitment(round_id=ctx.round.id, **body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/rounds/{round_id}/commitments", response_model=list[RoundCommitmentOut])
def list_commitments(ctx: RoundCtx = Depends(round_ctx), db: Session = Depends(get_db)):
    return db.query(Commitment).filter_by(round_id=ctx.round.id).all()


@router.post("/rounds/{round_id}/commitments/{commitment_id}/status", response_model=RoundCommitmentOut)
def update_commitment(
    commitment_id: str,
    body: RoundCommitmentStatusIn,
    ctx: RoundCtx = Depends(round_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    c = db.get(Commitment, commitment_id)
    if c is None or c.round_id != ctx.round.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Commitment not found")
    c.status = body.status
    if body.shares is not None:
        c.shares = body.shares
    db.commit()
    db.refresh(c)
    return c


@router.get("/rounds/{round_id}/summary")
def round_summary(ctx: RoundCtx = Depends(round_ctx), db: Session = Depends(get_db)):
    return svc.round_summary(db, ctx.round)


@router.post("/rounds/{round_id}/term-sheet", response_model=DocumentOut, status_code=201)
def term_sheet(
    ctx: RoundCtx = Depends(round_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    rnd = ctx.round
    entity = db.get(LegalEntity, rnd.entity_id)
    doc = docsvc.create_document(
        db,
        entity_id=rnd.entity_id,
        template_key="term_sheet",
        data={
            "round": rnd.name,
            "company": entity.name if entity else "",
            "instrument": rnd.instrument.value,
            "pre_money": str(rnd.pre_money),
            "target": str(rnd.target_amount),
            "price": str(rnd.price_per_share),
        },
        user_id=user.id,
        title=f"Term Sheet — {rnd.name}",
        subject_type="round",
        subject_id=rnd.id,
    )
    return docsvc.document_view(db, doc)


@router.post("/rounds/{round_id}/close")
def close_round(
    ctx: RoundCtx = Depends(round_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    result = svc.close_round(db, ctx.round, today_ist())
    if result.get("foreign_investors"):
        notifsvc.notify(
            db,
            user.id,
            "compliance",
            f"FC-GPR filing required — {ctx.round.name}",
            "A non-resident investor participated; FC-GPR is due within 30 days of allotment.",
        )
    return result

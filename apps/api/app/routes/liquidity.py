"""Company liquidity windows (FR-C-8): admin opens a buyback/tender event and
settles it; holders tender via the portal (see routes/portal.py)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EntityCtx, entity_ctx, get_current_user, require_write
from ..models.captable import Stakeholder
from ..models.identity import User
from ..models.liquidity import LiquidityEvent, Tender
from ..schemas import LiquidityEventIn
from ..services import liquidity as svc

router = APIRouter(tags=["liquidity"])


def _event(db: Session, event_id: str, entity_id: str) -> LiquidityEvent:
    ev = db.get(LiquidityEvent, event_id)
    if ev is None or ev.entity_id != entity_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Liquidity event not found")
    return ev


@router.post("/entities/{entity_id}/liquidity-events", status_code=201)
def create_event(
    body: LiquidityEventIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    if body.closes_on < body.opens_on:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "closes_on must be on or after opens_on")
    ev = LiquidityEvent(
        entity_id=ctx.entity.id, name=body.name, kind=body.kind,
        price_per_share=body.price_per_share, opens_on=body.opens_on,
        closes_on=body.closes_on, created_by=user.id,
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return svc.event_view(db, ev)


@router.get("/entities/{entity_id}/liquidity-events")
def list_events(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return [
        svc.event_view(db, ev)
        for ev in db.query(LiquidityEvent).filter_by(entity_id=ctx.entity.id)
    ]


@router.get("/entities/{entity_id}/liquidity-events/{event_id}/tenders")
def list_tenders(
    event_id: str, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    _event(db, event_id, ctx.entity.id)
    names = {s.id: s.name for s in db.query(Stakeholder).filter_by(entity_id=ctx.entity.id)}
    return [
        {
            "id": t.id,
            "stakeholder": names.get(t.stakeholder_id),
            "quantity": t.quantity,
            "status": t.status.value,
        }
        for t in db.query(Tender).filter_by(event_id=event_id)
    ]


@router.post("/entities/{entity_id}/liquidity-events/{event_id}/settle")
def settle_event(
    event_id: str, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ev = _event(db, event_id, ctx.entity.id)
    return svc.settle_event(db, ev)

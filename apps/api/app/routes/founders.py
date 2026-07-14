
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    FounderVestingCtx,
    entity_ctx,
    founder_vesting_ctx,
    require_write,
)
from ..models.captable import Stakeholder
from ..models.founders import FounderVesting
from ..schemas import FounderVestingIn, FounderVestingOut
from ..services import founders as svc

router = APIRouter(tags=["founder-vesting"])


@router.post("/entities/{entity_id}/founder-vesting", response_model=FounderVestingOut, status_code=201)
def create_vesting(
    body: FounderVestingIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    sh = db.get(Stakeholder, body.stakeholder_id)
    if sh is None or sh.entity_id != ctx.entity.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown stakeholder for this entity")
    fv = FounderVesting(entity_id=ctx.entity.id, **body.model_dump())
    db.add(fv)
    db.commit()
    db.refresh(fv)
    return svc.view(fv, today_ist())


@router.get("/entities/{entity_id}/founder-vesting", response_model=list[FounderVestingOut])
def list_vesting(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    today = today_ist()
    return [
        svc.view(fv, today)
        for fv in db.query(FounderVesting).filter_by(entity_id=ctx.entity.id)
    ]


@router.post("/founder-vesting/{vesting_id}/repurchase-unvested")
def repurchase(ctx: FounderVestingCtx = Depends(founder_vesting_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    return svc.repurchase_unvested(db, ctx.vesting, today_ist())

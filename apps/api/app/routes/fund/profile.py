from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ...db import get_db
from ...deps import (
    EntityCtx,
    FundCtx,
    PageCtx,
    entity_ctx,
    fund_ctx,
    get_current_user,
    page,
    require_write,
)
from ...models.fund import LP, Fund
from ...models.identity import User
from ...schemas import FundIn, FundOut, FundPlanIn, LPIn, LPOut
from ...services import fund as svc

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
def list_lps(
    ctx: FundCtx = Depends(fund_ctx),
    p: PageCtx = Depends(page),
    db: Session = Depends(get_db),
):
    return (
        db.query(LP)
        .filter_by(fund_id=ctx.fund.id)
        .order_by(LP.created_at)
        .offset(p.offset)
        .limit(p.limit)
        .all()
    )

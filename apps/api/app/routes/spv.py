
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import EntityCtx, SPVCtx, entity_ctx, get_current_user, require_write, spv_ctx
from ..models.entity import LegalEntity
from ..models.identity import User
from ..models.spv import CoInvestor, SPV
from ..schemas import (
    CoInvestorIn,
    CoInvestorOut,
    SPVIn,
    SPVInvestIn,
    SPVInvestmentOut,
    SPVOut,
)
from ..services import spv as svc

router = APIRouter(tags=["spv"])


@router.post("/entities/{entity_id}/spv", response_model=SPVOut, status_code=201)
def create_spv(
    body: SPVIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    if db.query(SPV).filter_by(entity_id=ctx.entity.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "SPV already exists for this entity")
    if body.portco_entity_id:
        portco = db.get(LegalEntity, body.portco_entity_id)
        # consent-gated cross-tenant linkage is deferred (ADR/HLD §6.2): same tenant only for now
        if portco is None or portco.tenant_id != ctx.entity.tenant_id:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Portco must be an entity in the same organisation"
            )
    spv = SPV(entity_id=ctx.entity.id, created_by=user.id, **body.model_dump())
    db.add(spv)
    db.commit()
    db.refresh(spv)
    return spv


@router.get("/entities/{entity_id}/spv", response_model=SPVOut)
def get_spv(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    spv = db.query(SPV).filter_by(entity_id=ctx.entity.id).first()
    if spv is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No SPV for this entity")
    return spv


@router.post("/spvs/{spv_id}/co-investors", response_model=CoInvestorOut, status_code=201)
def add_co_investor(
    body: CoInvestorIn, ctx: SPVCtx = Depends(spv_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ci = CoInvestor(spv_id=ctx.spv.id, **body.model_dump())
    db.add(ci)
    db.commit()
    db.refresh(ci)
    return ci


@router.get("/spvs/{spv_id}/co-investors", response_model=list[CoInvestorOut])
def list_co_investors(ctx: SPVCtx = Depends(spv_ctx), db: Session = Depends(get_db)):
    return db.query(CoInvestor).filter_by(spv_id=ctx.spv.id).all()


@router.post("/spvs/{spv_id}/co-investors/{co_investor_id}/contribute", response_model=CoInvestorOut)
def contribute(
    co_investor_id: str, ctx: SPVCtx = Depends(spv_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ci = db.get(CoInvestor, co_investor_id)
    if ci is None or ci.spv_id != ctx.spv.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Co-investor not found")
    return svc.contribute(db, ci)


@router.get("/spvs/{spv_id}/summary")
def spv_summary(ctx: SPVCtx = Depends(spv_ctx), db: Session = Depends(get_db)):
    return svc.summary(db, ctx.spv)


@router.post("/spvs/{spv_id}/invest", response_model=SPVInvestmentOut, status_code=201)
def invest(
    body: SPVInvestIn, ctx: SPVCtx = Depends(spv_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    return svc.invest_in_portco(
        db, ctx.spv, body.security_class_id, body.quantity, body.price_per_unit, today_ist()
    )

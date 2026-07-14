from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import ChargeCtx, EntityCtx, charge_ctx, entity_ctx, require_write
from ..models.registers import Charge, Registration, SignificantBeneficialOwner
from ..schemas import (
    ChargeIn,
    ChargeOut,
    RegistrationIn,
    RegistrationOut,
    SBOIn,
    SBOOut,
)

router = APIRouter(tags=["registers"])


# --- SBO register ---
@router.post("/entities/{entity_id}/sbo", response_model=SBOOut, status_code=201)
def add_sbo(body: SBOIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    sbo = SignificantBeneficialOwner(entity_id=ctx.entity.id, **body.model_dump())
    db.add(sbo)
    db.commit()
    db.refresh(sbo)
    return sbo


@router.get("/entities/{entity_id}/sbo", response_model=list[SBOOut])
def list_sbo(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(SignificantBeneficialOwner).filter_by(entity_id=ctx.entity.id).all()


# --- charges register ---
@router.post("/entities/{entity_id}/charges", response_model=ChargeOut, status_code=201)
def add_charge(body: ChargeIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    c = Charge(entity_id=ctx.entity.id, **body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/entities/{entity_id}/charges", response_model=list[ChargeOut])
def list_charges(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(Charge).filter_by(entity_id=ctx.entity.id).all()


@router.post("/charges/{charge_id}/satisfy", response_model=ChargeOut)
def satisfy_charge(ctx: ChargeCtx = Depends(charge_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    ctx.charge.satisfied = True
    db.commit()
    db.refresh(ctx.charge)
    return ctx.charge


# --- multi-state registrations ---
@router.post("/entities/{entity_id}/registrations", response_model=RegistrationOut, status_code=201)
def add_registration(
    body: RegistrationIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    r = Registration(entity_id=ctx.entity.id, **body.model_dump())
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@router.get("/entities/{entity_id}/registrations", response_model=list[RegistrationOut])
def list_registrations(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(Registration).filter_by(entity_id=ctx.entity.id).all()

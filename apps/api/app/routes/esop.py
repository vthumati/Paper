import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import EntityCtx, GrantCtx, entity_ctx, grant_ctx, get_current_user, require_write
from ..models.esop import ESOPScheme, Grant
from ..models.identity import User
from ..schemas import (
    ESOPSchemeIn,
    ESOPSchemeOut,
    EsopGrantIn,
    EsopGrantOut,
    ExerciseIn,
    ExerciseOut,
)
from ..services import esop as svc

router = APIRouter(tags=["esop"])


@router.post("/entities/{entity_id}/esop/schemes", response_model=ESOPSchemeOut, status_code=201)
def create_scheme(
    body: ESOPSchemeIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    scheme = ESOPScheme(
        entity_id=ctx.entity.id, name=body.name, pool_size=body.pool_size, created_by=user.id
    )
    db.add(scheme)
    db.commit()
    db.refresh(scheme)
    return scheme


@router.get("/entities/{entity_id}/esop/schemes", response_model=list[ESOPSchemeOut])
def list_schemes(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(ESOPScheme).filter_by(entity_id=ctx.entity.id).all()


@router.post("/entities/{entity_id}/esop/grants", response_model=EsopGrantOut, status_code=201)
def create_grant(
    body: EsopGrantIn,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    scheme = db.get(ESOPScheme, body.scheme_id)
    if scheme is None or scheme.entity_id != ctx.entity.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown scheme for this entity")
    grant = svc.create_grant(
        db,
        scheme,
        body.stakeholder_id,
        body.quantity,
        body.exercise_price,
        body.grant_date,
        body.cliff_months,
        body.total_months,
    )
    return svc.grant_view(db, grant, today_ist())


@router.get("/entities/{entity_id}/esop/grants", response_model=list[EsopGrantOut])
def list_grants(
    as_of: datetime.date | None = None,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    ref = as_of or today_ist()
    grants = db.query(Grant).filter_by(entity_id=ctx.entity.id).all()
    return [svc.grant_view(db, g, ref) for g in grants]


@router.get("/esop/grants/{grant_id}", response_model=EsopGrantOut)
def get_grant(
    as_of: datetime.date | None = None,
    ctx: GrantCtx = Depends(grant_ctx),
    db: Session = Depends(get_db),
):
    return svc.grant_view(db, ctx.grant, as_of or today_ist())


@router.post("/esop/grants/{grant_id}/exercise", response_model=ExerciseOut, status_code=201)
def exercise(
    body: ExerciseIn,
    as_of: datetime.date | None = None,
    ctx: GrantCtx = Depends(grant_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.exercise(
        db,
        ctx.grant,
        body.quantity,
        body.security_class_id,
        body.fmv_per_share,
        as_of or today_ist(),
        cashless=body.cashless,
    )

import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    ExerciseRequestCtx,
    GrantCtx,
    entity_ctx,
    exercise_request_ctx,
    get_current_user,
    grant_ctx,
    require_write,
)
from ..models.captable import Stakeholder
from ..models.esop import ESOPScheme, ExerciseRequest, ExerciseRequestStatus, Grant
from ..models.identity import User
from ..schemas import (
    ESOPSchemeIn,
    ESOPSchemeOut,
    EsopGrantIn,
    EsopGrantOut,
    ExerciseIn,
    ExerciseOut,
    ExerciseRequestDecideIn,
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
        grant_type=body.grant_type,
        security_class_id=body.security_class_id,
        fmv=body.fmv,
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


# --- employee exercise requests (asked in the portal, decided here) ---
@router.get("/entities/{entity_id}/exercise-requests")
def list_exercise_requests(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    out = []
    for r in db.query(ExerciseRequest).filter_by(entity_id=ctx.entity.id):
        grant = db.get(Grant, r.grant_id)
        sh = db.get(Stakeholder, grant.stakeholder_id) if grant else None
        out.append({
            "id": r.id,
            "employee": sh.name if sh else None,
            "grant_id": r.grant_id,
            "quantity": r.quantity,
            "cashless": r.cashless,
            "status": r.status.value,
        })
    return out


@router.post("/exercise-requests/{request_id}/decide")
def decide_exercise_request(
    body: ExerciseRequestDecideIn,
    ctx: ExerciseRequestCtx = Depends(exercise_request_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    req = ctx.request
    if req.status != ExerciseRequestStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Request is already decided")
    if not body.approve:
        req.status = ExerciseRequestStatus.REJECTED
        db.commit()
        return {"id": req.id, "status": req.status.value}
    if not body.security_class_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose the security class to issue into")
    grant = db.get(Grant, req.grant_id)
    ex = svc.exercise(
        db, grant, req.quantity, body.security_class_id,
        Decimal("0"),  # price off the current valuation (FR-L fallback)
        today_ist(), cashless=req.cashless,
    )
    req.status = ExerciseRequestStatus.APPROVED
    req.exercise_id = ex.id
    db.commit()
    return {"id": req.id, "status": req.status.value, "exercise_id": ex.id,
            "net_shares": ex.net_shares, "perquisite_value": str(ex.perquisite_value)}


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

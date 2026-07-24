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
from ..models.esop import (
    ESOPScheme,
    ExerciseRequest,
    ExerciseRequestStatus,
    ExerciseWindow,
    ForfeitureEvent,
    Grant,
)
from ..models.identity import User
from ..schemas import (
    DocumentOut,
    ESOPSchemeIn,
    ESOPSchemeOut,
    EsopGrantIn,
    EsopGrantOut,
    ExerciseIn,
    ExerciseOut,
    ExerciseRequestDecideIn,
    ExerciseWindowIn,
    ExerciseWindowOut,
    SBPAssumptionsIn,
)
from ..services import document as docsvc
from ..services import esop as svc
from ..services import sbp as sbpsvc

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


@router.get("/entities/{entity_id}/esop/overview")
def esop_overview(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    """ESOP dashboard: pool usage, option states, grantees, top grants."""
    return svc.esop_overview(db, ctx.entity.id, today_ist())


@router.post(
    "/entities/{entity_id}/esop/schemes/{scheme_id}/pack", response_model=list[DocumentOut]
)
def scheme_pack(
    scheme_id: str,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate the ESOP-adoption pack (board resolution + EGM notice + policy)."""
    require_write(ctx.role)
    scheme = db.get(ESOPScheme, scheme_id)
    if scheme is None or scheme.entity_id != ctx.entity.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Scheme not found")
    docs = svc.generate_scheme_pack(db, scheme, user.id)
    return [docsvc.document_view(db, d) for d in docs]


# --- share-based-payment expense (Ind AS 102, FR-D-6) ---
def _assumptions(volatility: float, risk_free: float, expected_life: float, dividend_yield: float) -> dict:
    return {
        "volatility": volatility, "risk_free": risk_free,
        "expected_life": expected_life, "dividend_yield": dividend_yield,
    }


@router.get("/entities/{entity_id}/esop/expense")
def esop_expense(
    volatility: float = 0.5,
    risk_free: float = 0.07,
    expected_life: float = 5.0,
    dividend_yield: float = 0.0,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    return sbpsvc.expense_report(
        db, ctx.entity.id, _assumptions(volatility, risk_free, expected_life, dividend_yield), today_ist()
    )


@router.post("/entities/{entity_id}/esop/expense-report", response_model=DocumentOut, status_code=201)
def esop_expense_report(
    body: SBPAssumptionsIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    a = _assumptions(
        float(body.volatility), float(body.risk_free), float(body.expected_life), float(body.dividend_yield)
    )
    rep = sbpsvc.expense_report(db, ctx.entity.id, a, today_ist())
    grant_lines = "\n".join(
        f"  {g['grant_type'].upper()} × {g['quantity']:,}: FV/unit ₹{g['fair_value_per_unit']} "
        f"→ ₹{g['total_fair_value']} (recognised ₹{g['recognized_to_date']})"
        for g in rep["grants"]
    ) or "  No priced grants."
    fy_lines = "\n".join(f"  {r['fy']}: ₹{r['expense']}" for r in rep["by_financial_year"]) or "  —"
    entity = ctx.entity
    doc = docsvc.create_document(
        db,
        entity_id=ctx.entity.id,
        template_key="esop_expense",
        data={
            "company": entity.name,
            "date": rep["as_of"],
            "assumptions": f"volatility {body.volatility}, risk-free {body.risk_free}, "
            f"expected life {body.expected_life}y, dividend yield {body.dividend_yield}",
            "grants": grant_lines,
            "by_fy": fy_lines,
            "total_fair_value": rep["totals"]["total_fair_value"],
            "recognized_to_date": rep["totals"]["recognized_to_date"],
            "unrecognized": rep["totals"]["unrecognized"],
        },
        user_id=user.id,
        title=f"ESOP expense (Ind AS 102) — {rep['as_of']}",
        subject_type="esop_expense",
        subject_id=ctx.entity.id,
    )
    return docsvc.document_view(db, doc)


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


# --- exercise windows (FR-D-4): opt-in periods gating exercise ---
@router.post("/entities/{entity_id}/exercise-windows", response_model=ExerciseWindowOut, status_code=201)
def create_exercise_window(
    body: ExerciseWindowIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    if body.closes_on < body.opens_on:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "closes_on must be on or after opens_on")
    w = ExerciseWindow(
        entity_id=ctx.entity.id, name=body.name,
        opens_on=body.opens_on, closes_on=body.closes_on, created_by=user.id,
    )
    db.add(w)
    db.commit()
    db.refresh(w)
    return w


@router.get("/entities/{entity_id}/exercise-windows")
def list_exercise_windows(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return svc.exercise_windows(db, ctx.entity.id, today_ist())


# --- employee exercise requests (asked in the portal, decided here) ---
@router.get("/entities/{entity_id}/exercise-requests")
def list_exercise_requests(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    out = []
    ref = today_ist()
    for r in db.query(ExerciseRequest).filter_by(entity_id=ctx.entity.id):
        grant = db.get(Grant, r.grant_id)
        sh = db.get(Stakeholder, grant.stakeholder_id) if grant else None
        # estimated perquisite + TDS at the current FMV, so the approver sees the
        # tax that will be withheld before deciding (FR-D-3)
        est = svc.exercise_tax_estimate(db, grant, r.quantity, ref) if grant else {}
        out.append({
            "id": r.id,
            "employee": sh.name if sh else None,
            "grant_id": r.grant_id,
            "quantity": r.quantity,
            "cashless": r.cashless,
            "status": r.status.value,
            "perquisite": est.get("perquisite"),
            "estimated_tds": est.get("tds"),
        })
    return out


@router.post("/exercise-requests/{request_id}/decide")
def decide_exercise_request(
    body: ExerciseRequestDecideIn,
    ctx: ExerciseRequestCtx = Depends(exercise_request_ctx),
    user: User = Depends(get_current_user),
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
        issued_by=user.id,  # board approval → issue shares + share certificate
    )
    req.status = ExerciseRequestStatus.APPROVED
    req.exercise_id = ex.id
    db.commit()
    tax = svc.perquisite_tax(ex.perquisite_value)
    return {"id": req.id, "status": req.status.value, "exercise_id": ex.id,
            "net_shares": ex.net_shares, "perquisite_value": str(ex.perquisite_value),
            "tds": tax["tds"]}


@router.post("/esop/grants/{grant_id}/exercise", response_model=ExerciseOut, status_code=201)
def exercise(
    body: ExerciseIn,
    as_of: datetime.date | None = None,
    ctx: GrantCtx = Depends(grant_ctx),
    user: User = Depends(get_current_user),
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
        issued_by=user.id,
    )


@router.post("/esop/grants/{grant_id}/letter", response_model=DocumentOut, status_code=201)
def grant_letter(
    ctx: GrantCtx = Depends(grant_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate the employee's grant letter (award terms + vesting schedule)."""
    require_write(ctx.role)
    doc = svc.generate_grant_letter(db, ctx.grant, user.id)
    return docsvc.document_view(db, doc)


@router.get("/entities/{entity_id}/esop/forfeitures")
def list_forfeitures(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    """Auditable option-forfeiture / true-up log for the entity (FR-D/R-4)."""
    names = {s.id: s.name for s in db.query(Stakeholder).filter_by(entity_id=ctx.entity.id)}
    return [
        {
            "id": f.id,
            "stakeholder": names.get(f.stakeholder_id),
            "grant_id": f.grant_id,
            "lapsed_quantity": f.lapsed_quantity,
            "vested_retained": f.vested_retained,
            "reason": f.reason,
            "date": f.date.isoformat(),
        }
        for f in db.query(ForfeitureEvent)
        .filter_by(entity_id=ctx.entity.id)
        .order_by(ForfeitureEvent.date.desc())
    ]

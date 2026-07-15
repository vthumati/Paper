import datetime
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..clock import now_ist, today_ist
from ..db import get_db
from ..deps import EntityCtx, entity_ctx, get_current_user, get_owned, require_write
from ..models.identity import User
from ..models.valuation import ValuationEstimate, ValuationReport
from ..schemas import (
    CurrentFmvOut,
    DocumentOut,
    SmartfillOut,
    ValuationEstimateIn,
    ValuationEstimateOut,
    ValuationIn,
    ValuationOut,
)
from ..services import document as docsvc
from ..services import startup_valuation as sv
from ..services import valuation as svc

router = APIRouter(tags=["valuations"])


@router.post("/entities/{entity_id}/valuations", response_model=ValuationOut, status_code=201)
def create_valuation(
    body: ValuationIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    v = ValuationReport(entity_id=ctx.entity.id, created_by=user.id, **body.model_dump())
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


@router.get("/entities/{entity_id}/valuations", response_model=list[ValuationOut])
def list_valuations(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return (
        db.query(ValuationReport)
        .filter_by(entity_id=ctx.entity.id)
        .order_by(ValuationReport.valuation_date.desc())
        .all()
    )


@router.get("/entities/{entity_id}/valuations/current", response_model=CurrentFmvOut)
def current_valuation(
    as_of: datetime.date | None = None,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    v = svc.current_valuation(db, ctx.entity.id, as_of or today_ist())
    if v is None:
        return CurrentFmvOut(fmv_per_share=None, valuation_id=None, valuation_date=None)
    return CurrentFmvOut(
        fmv_per_share=v.fmv_per_share, valuation_id=v.id, valuation_date=v.valuation_date
    )


# --- self-serve indicative valuation estimates (FR-L-2) ---
@router.get(
    "/entities/{entity_id}/valuation-estimates/scorecard-factors"
)
def scorecard_factors(ctx: EntityCtx = Depends(entity_ctx)):
    return {
        "factors": [
            {"key": f["key"], "label": f["label"], "weight": str(f["weight"])}
            for f in sv.SCORECARD_FACTORS
        ]
    }


@router.get(
    "/entities/{entity_id}/valuation-estimates/smartfill", response_model=SmartfillOut
)
def valuation_smartfill(
    growth_pct: float = 20.0,
    years: int = 5,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    return sv.smartfill(db, ctx.entity.id, Decimal(str(growth_pct)), max(1, min(years, 15)))


@router.get(
    "/entities/{entity_id}/valuation-estimates", response_model=list[ValuationEstimateOut]
)
def list_estimates(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return (
        db.query(ValuationEstimate)
        .filter_by(entity_id=ctx.entity.id)
        .order_by(ValuationEstimate.created_at.desc())
        .all()
    )


@router.post(
    "/entities/{entity_id}/valuation-estimates",
    response_model=ValuationEstimateOut,
    status_code=201,
)
def create_estimate(
    body: ValuationEstimateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    results = sv.compute_estimate(db, ctx.entity.id, body)
    est = ValuationEstimate(
        entity_id=ctx.entity.id,
        label=body.label,
        inputs=body.model_dump(mode="json", exclude={"label", "save"}),
        results=results,
        created_by=user.id,
    )
    if body.save:
        db.add(est)
        db.commit()
        db.refresh(est)
    else:
        # not persisted — populate the fields the response model needs
        est.id = ""
        est.created_at = now_ist()
    return est


@router.post(
    "/entities/{entity_id}/valuation-estimates/{estimate_id}/report",
    response_model=DocumentOut,
    status_code=201,
)
def estimate_report(
    estimate_id: str,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    est = get_owned(db, ValuationEstimate, estimate_id, ctx.entity.id, "valuation estimate")
    return docsvc.document_view(db, sv.generate_report(db, est, user.id))

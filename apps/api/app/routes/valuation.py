import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import EntityCtx, entity_ctx, get_current_user, require_write
from ..models.identity import User
from ..models.valuation import ValuationReport
from ..schemas import CurrentFmvOut, ValuationIn, ValuationOut
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

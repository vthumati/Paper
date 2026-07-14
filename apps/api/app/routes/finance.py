from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EntityCtx, entity_ctx, require_write
from ..models.finance import FinancialSnapshot
from ..schemas import SnapshotIn
from ..services.finance import runway_summary

router = APIRouter(tags=["finance"])


@router.post("/entities/{entity_id}/finance/snapshots", status_code=201)
def add_snapshot(
    body: SnapshotIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    snap = (
        db.query(FinancialSnapshot)
        .filter_by(entity_id=ctx.entity.id, period=body.period)
        .first()
    )
    if snap is None:
        snap = FinancialSnapshot(entity_id=ctx.entity.id, period=body.period)
        db.add(snap)
    snap.cash_balance = body.cash_balance
    snap.monthly_burn = body.monthly_burn
    snap.revenue = body.revenue
    db.commit()
    return {"id": snap.id, "period": snap.period}


@router.get("/entities/{entity_id}/finance/runway")
def runway(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return runway_summary(db, ctx.entity.id)

import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    ObligationCtx,
    PageCtx,
    entity_ctx,
    get_current_user,
    obligation_ctx,
    page,
    require_write,
)
from ..models.compliance import ComplianceObligation
from ..models.identity import User
from ..schemas import ComplianceGenerateIn, ObligationOut, ObligationStatusIn
from ..services import compliance as svc
from ..services import notification as notifsvc

router = APIRouter(tags=["compliance"])


@router.post("/entities/{entity_id}/compliance/generate", response_model=list[ObligationOut])
def generate(
    body: ComplianceGenerateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    n = svc.generate_for_fy(db, ctx.entity.id, body.financial_year_end)
    if n:
        notifsvc.notify(
            db,
            user.id,
            "compliance",
            "Compliance calendar generated",
            f"{n} statutory obligation(s) added.",
        )
    return _list(db, ctx.entity.id, today_ist())


@router.post("/entities/{entity_id}/compliance/generate-periodic", response_model=list[ObligationOut])
def generate_periodic(
    body: ComplianceGenerateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    n = svc.generate_periodic(db, ctx.entity.id, body.financial_year_end)
    notifsvc.notify(
        db, user.id, "compliance", "Periodic GST/TDS schedule generated",
        f"{n} recurring obligations on record.",
    )
    return _list(db, ctx.entity.id, today_ist())


@router.post("/entities/{entity_id}/compliance/generate-aif", response_model=list[ObligationOut])
def generate_aif(
    body: ComplianceGenerateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    n = svc.generate_aif(db, ctx.entity.id, body.financial_year_end)
    notifsvc.notify(
        db, user.id, "compliance", "SEBI AIF calendar generated",
        f"{n} SEBI obligations on record.",
    )
    return _list(db, ctx.entity.id, today_ist())


@router.get("/entities/{entity_id}/compliance/health")
def compliance_health(
    as_of: datetime.date | None = None,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    return svc.health_score(db, ctx.entity.id, as_of or today_ist())


@router.get("/entities/{entity_id}/compliance", response_model=list[ObligationOut])
def list_obligations(
    as_of: datetime.date | None = None,
    p: PageCtx = Depends(page),
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    return _list(db, ctx.entity.id, as_of or today_ist(), p.limit, p.offset)


@router.post("/compliance/{obligation_id}/status", response_model=ObligationOut)
def update_status(
    body: ObligationStatusIn,
    ctx: ObligationCtx = Depends(obligation_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    ob = ctx.obligation
    ob.status = body.status
    if body.srn is not None:
        ob.srn = body.srn
    if body.assignee is not None:
        ob.assignee = body.assignee
    db.commit()
    db.refresh(ob)
    return svc.obligation_view(ob, today_ist())


def _list(
    db: Session, entity_id: str, as_of: datetime.date, limit: int = 500, offset: int = 0
) -> list[dict]:
    obs = (
        db.query(ComplianceObligation)
        .filter_by(entity_id=entity_id)
        .order_by(ComplianceObligation.due_date)
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [svc.obligation_view(o, as_of) for o in obs]

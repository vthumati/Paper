from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EntityCtx, ProspectCtx, entity_ctx, prospect_ctx, require_write
from ..models.crm import ProspectInvestor
from ..schemas import ProspectIn, ProspectOut, ProspectStageIn
from ..services import crm as svc

router = APIRouter(tags=["investor-crm"])


@router.post("/entities/{entity_id}/investor-pipeline", response_model=ProspectOut, status_code=201)
def add_prospect(
    body: ProspectIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    p = ProspectInvestor(entity_id=ctx.entity.id, **body.model_dump())
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.get("/entities/{entity_id}/investor-pipeline", response_model=list[ProspectOut])
def list_pipeline(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(ProspectInvestor).filter_by(entity_id=ctx.entity.id).all()


@router.get("/entities/{entity_id}/investor-pipeline/summary")
def pipeline_summary(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return svc.pipeline_summary(db, ctx.entity.id)


@router.post("/pipeline/{prospect_id}/stage", response_model=ProspectOut)
def update_stage(
    body: ProspectStageIn, ctx: ProspectCtx = Depends(prospect_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ctx.prospect.stage = body.stage
    if body.notes is not None:
        ctx.prospect.notes = body.notes
    db.commit()
    db.refresh(ctx.prospect)
    return ctx.prospect


@router.post("/pipeline/{prospect_id}/convert")
def convert(ctx: ProspectCtx = Depends(prospect_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    return svc.convert_to_commitment(db, ctx.prospect)

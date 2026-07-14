from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EntityCtx, TenantCtx, entity_ctx, require_write, tenant_ctx
from ..models.entity import EntityType, LegalEntity
from ..schemas import EntityIn, EntityOut, StageIn
from ..services.stage import stage_guide

router = APIRouter(tags=["entities"])

STAGED_TYPES = (EntityType.PVT_LTD, EntityType.LLP, EntityType.OPC)


@router.post(
    "/tenants/{tenant_id}/entities",
    response_model=EntityOut,
    status_code=status.HTTP_201_CREATED,
)
def create_entity(
    body: EntityIn,
    ctx: TenantCtx = Depends(tenant_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    entity = LegalEntity(tenant_id=ctx.tenant.id, **body.model_dump())
    db.add(entity)
    db.commit()
    db.refresh(entity)
    return entity


@router.get("/tenants/{tenant_id}/entities", response_model=list[EntityOut])
def list_entities(
    ctx: TenantCtx = Depends(tenant_ctx),
    db: Session = Depends(get_db),
):
    return db.query(LegalEntity).filter_by(tenant_id=ctx.tenant.id).all()


@router.get("/entities/{entity_id}", response_model=EntityOut)
def get_entity(ctx: EntityCtx = Depends(entity_ctx)):
    return ctx.entity


# --- lifecycle stage (companies only) ---
@router.get("/entities/{entity_id}/stage-guide")
def get_stage_guide(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    if ctx.entity.type not in STAGED_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stages apply to companies only")
    return stage_guide(db, ctx.entity)


@router.put("/entities/{entity_id}/stage")
def set_stage(
    body: StageIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    if ctx.entity.type not in STAGED_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stages apply to companies only")
    ctx.entity.stage = body.stage
    db.commit()
    return stage_guide(db, ctx.entity)

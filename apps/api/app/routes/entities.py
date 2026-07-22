from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EntityCtx, TenantCtx, entity_ctx, require_admin, require_write, tenant_ctx
from ..models.entity import EntityType, LegalEntity
from ..models.identity import Role
from ..schemas import EntityIn, EntityOut, PackIn, StageIn, TeardownIn
from ..services import teardown
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


@router.put("/entities/{entity_id}/pack")
def set_pack(
    body: PackIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    # the pack is the commercial tier — owner/admin only, not any member
    require_admin(ctx.role)
    if ctx.entity.type not in STAGED_TYPES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Feature packs apply to companies only")
    ctx.entity.pack = body.pack
    db.commit()
    return stage_guide(db, ctx.entity)


# --- full teardown (destructive) ---
@router.get("/entities/{entity_id}/teardown-preview")
def entity_teardown_preview(
    ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    """Dry run: what deleting this entity would remove (row counts by area)."""
    if ctx.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can delete an entity")
    return teardown.preview_entity_teardown(db, ctx.entity)


@router.post("/entities/{entity_id}/teardown")
def entity_teardown(
    body: TeardownIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    """Permanently delete this entity and every record that hangs off it.
    Owner-only; the request must echo the entity's exact name."""
    if ctx.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the owner can delete an entity")
    if body.confirm_name.strip() != ctx.entity.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Confirmation name does not match")
    deleted = teardown.teardown_entity(db, ctx.entity)
    return {"deleted_rows": deleted}

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import TenantCtx, get_current_user, tenant_ctx
from ..models.entity import LegalEntity
from ..models.identity import Membership, Role, Tenant, User
from ..schemas import TenantIn, TenantOut, TeardownIn
from ..services import teardown

router = APIRouter(tags=["tenants"])


@router.post("/tenants", response_model=TenantOut, status_code=status.HTTP_201_CREATED)
def create_tenant(
    body: TenantIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tenant = Tenant(name=body.name, type=body.type)
    db.add(tenant)
    db.flush()
    db.add(Membership(user_id=user.id, tenant_id=tenant.id, role=Role.OWNER))
    db.commit()
    db.refresh(tenant)
    return tenant


@router.get("/tenants", response_model=list[TenantOut])
def list_tenants(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(Tenant)
        .join(Membership, Membership.tenant_id == Tenant.id)
        .filter(Membership.user_id == user.id)
        .all()
    )


@router.get("/tenants/{tenant_id}", response_model=TenantOut)
def get_tenant(ctx: TenantCtx = Depends(tenant_ctx)):
    return ctx.tenant


@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tenant(ctx: TenantCtx = Depends(tenant_ctx), db: Session = Depends(get_db)):
    """Delete a workspace. Owner-only, and only when it holds no entities —
    entities carry the regulated record, so they must be removed first (guards
    against wiping a whole company's data with one call)."""
    if ctx.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can delete it")
    if db.query(LegalEntity.id).filter_by(tenant_id=ctx.tenant.id).first():
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Workspace still has entities — remove them before deleting the workspace",
        )
    db.query(Membership).filter_by(tenant_id=ctx.tenant.id).delete()
    db.delete(ctx.tenant)
    db.commit()


# --- full teardown (destructive): workspace + all entities and their data ---
@router.get("/tenants/{tenant_id}/teardown-preview")
def workspace_teardown_preview(
    ctx: TenantCtx = Depends(tenant_ctx), db: Session = Depends(get_db)
):
    if ctx.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can delete it")
    return teardown.preview_workspace_teardown(db, ctx.tenant)


@router.post("/tenants/{tenant_id}/teardown")
def workspace_teardown(
    body: TeardownIn, ctx: TenantCtx = Depends(tenant_ctx), db: Session = Depends(get_db)
):
    """Permanently delete the workspace and every entity, member and record
    inside it. Owner-only; the request must echo the workspace's exact name."""
    if ctx.role != Role.OWNER:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only the workspace owner can delete it")
    if body.confirm_name.strip() != ctx.tenant.name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Confirmation name does not match")
    deleted = teardown.teardown_workspace(db, ctx.tenant)
    return {"deleted_rows": deleted}

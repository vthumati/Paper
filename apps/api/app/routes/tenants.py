from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import TenantCtx, get_current_user, tenant_ctx
from ..models.identity import Membership, Role, Tenant, User
from ..schemas import TenantIn, TenantOut

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

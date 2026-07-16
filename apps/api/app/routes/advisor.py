"""External advisor access (FR-J-2, Mantle gap): a company grants a law firm /
CA / CS scoped access to its entity; the advisor sees a cross-tenant console of
every client entity they can act on. Access is enforced in deps._entity_role,
so an advisor reaches the normal entity workspace with their granted role."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (
    EntityCtx,
    entity_ctx,
    get_current_user,
    require_admin,
    require_verified_email,
)
from ..models.entity import LegalEntity
from ..models.identity import AdvisorAccess, Role, Tenant, User
from ..schemas import AdvisorAccessIn, AdvisorAccessOut, AdvisorEntityOut

router = APIRouter(tags=["advisor"])


@router.post(
    "/entities/{entity_id}/advisor-access", response_model=AdvisorAccessOut, status_code=201
)
def grant_advisor_access(
    body: AdvisorAccessIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(ctx.role)
    existing = (
        db.query(AdvisorAccess)
        .filter_by(entity_id=ctx.entity.id, email=body.email)
        .first()
    )
    if existing:
        existing.firm_name = body.firm_name
        existing.role = Role(body.role)
        db.commit()
        db.refresh(existing)
        return existing
    adv = AdvisorAccess(
        entity_id=ctx.entity.id,
        email=body.email,
        firm_name=body.firm_name,
        role=Role(body.role),
        invited_by=user.id,
    )
    db.add(adv)
    db.commit()
    db.refresh(adv)
    return adv


@router.get("/entities/{entity_id}/advisor-access", response_model=list[AdvisorAccessOut])
def list_advisor_access(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(AdvisorAccess).filter_by(entity_id=ctx.entity.id).all()


@router.delete("/entities/{entity_id}/advisor-access/{advisor_id}", status_code=204)
def revoke_advisor_access(
    advisor_id: str,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    require_admin(ctx.role)
    adv = db.get(AdvisorAccess, advisor_id)
    if adv is None or adv.entity_id != ctx.entity.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Advisor access not found")
    db.delete(adv)
    db.commit()


@router.get("/advisor/entities", response_model=list[AdvisorEntityOut])
def my_advised_entities(
    user: User = Depends(require_verified_email), db: Session = Depends(get_db)
):
    """Cross-tenant console: every client entity this advisor can act on."""
    out = []
    for adv in db.query(AdvisorAccess).filter_by(email=user.email):
        entity = db.get(LegalEntity, adv.entity_id)
        if entity is None:
            continue
        tenant = db.get(Tenant, entity.tenant_id)
        out.append(
            AdvisorEntityOut(
                entity_id=entity.id,
                entity_name=entity.name,
                entity_type=entity.type.value,
                tenant_name=tenant.name if tenant else "",
                firm_name=adv.firm_name,
                role=adv.role,
            )
        )
    return out

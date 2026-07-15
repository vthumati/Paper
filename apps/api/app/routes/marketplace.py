from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import (
    EngagementCtx,
    EntityCtx,
    engagement_ctx,
    entity_ctx,
    get_current_user,
    require_write,
)
from ..models.identity import User
from ..models.marketplace import ProviderCategory, ServiceEngagement, ServiceProvider
from ..schemas import (
    ProviderIn,
    ProviderOut,
    ServiceEngagementIn,
    ServiceEngagementOut,
    ServiceEngagementStatusIn,
)
from ..services import marketplace as svc

router = APIRouter(tags=["marketplace"])


# --- provider directory (platform-level) ---
@router.get("/service-providers", response_model=list[ProviderOut])
def list_providers(
    category: ProviderCategory | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(ServiceProvider).filter_by(active=True)
    if category is not None:
        q = q.filter_by(category=category)
    return q.all()


@router.post("/service-providers", response_model=ProviderOut, status_code=201)
def register_provider(
    body: ProviderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # open registration, but only platform-verified providers can be engaged;
    # a platform admin's own registrations are trusted immediately
    p = ServiceProvider(
        **body.model_dump(), verified=user.email in settings.platform_admin_emails
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


@router.post("/service-providers/{provider_id}/verify", response_model=ProviderOut)
def verify_provider(
    provider_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if user.email not in settings.platform_admin_emails:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Platform admin required")
    p = db.get(ServiceProvider, provider_id)
    if p is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Provider not found")
    p.verified = True
    db.commit()
    db.refresh(p)
    return p


# --- engagements (entity-scoped) ---
@router.post("/entities/{entity_id}/engagements", response_model=ServiceEngagementOut, status_code=201)
def create_engagement(
    body: ServiceEngagementIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    provider = db.get(ServiceProvider, body.provider_id)
    if provider is None or not provider.active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown provider")
    if not provider.verified:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Provider is not yet platform-verified"
        )
    eng = ServiceEngagement(
        entity_id=ctx.entity.id,
        provider_id=body.provider_id,
        scope=body.scope,
        created_by=user.id,
    )
    db.add(eng)
    db.commit()
    db.refresh(eng)
    return svc.engagement_view(db, eng)


@router.get("/entities/{entity_id}/engagements", response_model=list[ServiceEngagementOut])
def list_engagements(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    engs = db.query(ServiceEngagement).filter_by(entity_id=ctx.entity.id).all()
    return [svc.engagement_view(db, e) for e in engs]


@router.post("/engagements/{engagement_id}/status", response_model=ServiceEngagementOut)
def update_status(
    body: ServiceEngagementStatusIn,
    ctx: EngagementCtx = Depends(engagement_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    eng = ctx.engagement
    eng.status = body.status
    if body.deliverable_doc_id is not None:
        eng.deliverable_doc_id = body.deliverable_doc_id
    db.commit()
    db.refresh(eng)
    return svc.engagement_view(db, eng)

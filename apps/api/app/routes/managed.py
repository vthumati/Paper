from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (
    EntityCtx,
    SubscriptionCtx,
    entity_ctx,
    get_current_user,
    require_write,
    subscription_ctx,
)
from ..models.identity import User
from ..models.managed import AdminSubscription, AuditEngagement, TouchpointMeeting
from ..schemas import (
    AdminSubscriptionIn,
    AdminSubscriptionOut,
    AuditEngagementIn,
    AuditEngagementOut,
    AuditStatusIn,
    TouchpointIn,
    TouchpointOut,
)

router = APIRouter(tags=["managed-admin"])


@router.post("/entities/{entity_id}/admin-subscription", response_model=AdminSubscriptionOut, status_code=201)
def subscribe(
    body: AdminSubscriptionIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    if db.query(AdminSubscription).filter_by(entity_id=ctx.entity.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Subscription already exists for this entity")
    sub = AdminSubscription(
        entity_id=ctx.entity.id, tier=body.tier, provider_id=body.provider_id, created_by=user.id
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.get("/entities/{entity_id}/admin-subscription", response_model=AdminSubscriptionOut)
def get_subscription(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    sub = db.query(AdminSubscription).filter_by(entity_id=ctx.entity.id).first()
    if sub is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No subscription for this entity")
    return sub


@router.post("/admin-subscriptions/{subscription_id}/touchpoints", response_model=TouchpointOut, status_code=201)
def add_touchpoint(
    body: TouchpointIn, ctx: SubscriptionCtx = Depends(subscription_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    tp = TouchpointMeeting(subscription_id=ctx.subscription.id, **body.model_dump())
    db.add(tp)
    db.commit()
    db.refresh(tp)
    return tp


@router.post("/admin-subscriptions/{subscription_id}/audits", response_model=AuditEngagementOut, status_code=201)
def schedule_audit(
    body: AuditEngagementIn, ctx: SubscriptionCtx = Depends(subscription_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    audit = AuditEngagement(
        subscription_id=ctx.subscription.id, type=body.type, period_label=body.period_label
    )
    db.add(audit)
    db.commit()
    db.refresh(audit)
    return audit


@router.post("/admin-subscriptions/{subscription_id}/audits/{audit_id}/status", response_model=AuditEngagementOut)
def update_audit(
    audit_id: str,
    body: AuditStatusIn,
    ctx: SubscriptionCtx = Depends(subscription_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    audit = db.get(AuditEngagement, audit_id)
    if audit is None or audit.subscription_id != ctx.subscription.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Audit not found")
    audit.status = body.status
    if body.findings is not None:
        audit.findings = body.findings
    db.commit()
    db.refresh(audit)
    return audit

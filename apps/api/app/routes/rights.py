
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    RightsIssueCtx,
    entity_ctx,
    require_write,
    rights_issue_ctx,
)
from ..models.captable import RightsIssue, SecurityClass
from ..schemas import RightsIssueIn, RightsIssueOut, RightsSubscriptionIn
from ..services import rights as svc

router = APIRouter(tags=["rights-issue"])


@router.post("/entities/{entity_id}/rights-issues", response_model=RightsIssueOut, status_code=201)
def create_rights_issue(
    body: RightsIssueIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    sc = db.get(SecurityClass, body.security_class_id)
    if not sc or sc.entity_id != ctx.entity.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown security class for this entity")
    if body.ratio_num <= 0 or body.ratio_den <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Ratio must be positive")
    ri = RightsIssue(
        entity_id=ctx.entity.id,
        security_class_id=body.security_class_id,
        ratio_num=body.ratio_num,
        ratio_den=body.ratio_den,
        price_per_unit=body.price_per_unit,
        record_date=body.record_date or today_ist(),
    )
    db.add(ri)
    db.commit()
    db.refresh(ri)
    return ri


@router.get("/entities/{entity_id}/rights-issues", response_model=list[RightsIssueOut])
def list_rights_issues(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(RightsIssue).filter_by(entity_id=ctx.entity.id).all()


@router.get("/rights-issues/{rights_issue_id}/entitlements")
def entitlements(ctx: RightsIssueCtx = Depends(rights_issue_ctx), db: Session = Depends(get_db)):
    return svc.entitlements(db, ctx.rights_issue)


@router.post("/rights-issues/{rights_issue_id}/subscriptions", status_code=201)
def subscribe(
    body: RightsSubscriptionIn,
    ctx: RightsIssueCtx = Depends(rights_issue_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    sub = svc.subscribe(db, ctx.rights_issue, body.stakeholder_id, body.quantity)
    return {"id": sub.id, "stakeholder_id": sub.stakeholder_id, "quantity": sub.quantity}


@router.post("/rights-issues/{rights_issue_id}/close")
def close(ctx: RightsIssueCtx = Depends(rights_issue_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    return svc.close(db, ctx.rights_issue, today_ist())

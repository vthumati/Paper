from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import PageCtx, get_current_user, page
from ..models.audit import AuditLogEntry
from ..models.identity import User
from ..models.notification import Notification
from ..schemas import AuditEntryOut, NotificationOut

router = APIRouter(tags=["activity"])


@router.get("/audit-log", response_model=list[AuditEntryOut])
def my_audit_log(
    limit: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(AuditLogEntry)
        .filter_by(actor_user_id=user.id)
        .order_by(AuditLogEntry.created_at.desc())
        .limit(min(limit, 200))
        .all()
    )


@router.get("/notifications", response_model=list[NotificationOut])
def my_notifications(
    unread_only: bool = False,
    p: PageCtx = Depends(page),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    q = db.query(Notification).filter_by(user_id=user.id)
    if unread_only:
        q = q.filter_by(read=False)
    return (
        q.order_by(Notification.created_at.desc()).offset(p.offset).limit(p.limit).all()
    )


@router.post("/notifications/{notification_id}/read", response_model=NotificationOut)
def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    n = db.get(Notification, notification_id)
    if n is None or n.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
    n.read = True
    db.commit()
    db.refresh(n)
    return n


@router.post("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.query(Notification).filter_by(user_id=user.id, read=False).update({"read": True})
    db.commit()
    return {"ok": True}

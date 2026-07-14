"""Notification service (FR-M-3). `notify` is callable from any module to
create an in-app notification for a user."""
from sqlalchemy.orm import Session

from ..models.notification import Notification


def notify(db: Session, user_id: str, type_: str, title: str, body: str | None = None) -> Notification:
    n = Notification(user_id=user_id, type=type_, title=title, body=body)
    db.add(n)
    db.commit()
    db.refresh(n)
    return n

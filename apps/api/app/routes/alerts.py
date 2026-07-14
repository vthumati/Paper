
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import get_current_user
from ..models.identity import User
from ..services import alerts as svc

router = APIRouter(tags=["alerts"])


@router.get("/alerts")
def my_alerts(
    within_days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return svc.alerts_for_user(db, user, today_ist(), within_days)


@router.post("/alerts/sweep")
def sweep(
    within_days: int = 30,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    created = svc.sweep(db, user, today_ist(), within_days)
    return {"notifications_created": created}

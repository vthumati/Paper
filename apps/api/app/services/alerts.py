"""Alerts / reminder engine. Aggregates time-sensitive items (overdue or
due-soon compliance obligations and contract renewals) across the entities a
user can access, and can sweep them into in-app notifications."""
import datetime

from sqlalchemy.orm import Session

from ..models.clm import Contract, ContractStatus
from ..models.compliance import ComplianceObligation, ObligationStatus
from ..models.entity import LegalEntity
from ..models.identity import Membership, User
from ..models.notification import Notification
from . import notification as notifsvc

_OPEN = {ObligationStatus.DUE, ObligationStatus.IN_PREP}


def _user_entities(db: Session, user: User) -> list[LegalEntity]:
    tenant_ids = [m.tenant_id for m in db.query(Membership).filter_by(user_id=user.id)]
    if not tenant_ids:
        return []
    return db.query(LegalEntity).filter(LegalEntity.tenant_id.in_(tenant_ids)).all()


def alerts_for_user(db: Session, user: User, as_of: datetime.date, within_days: int = 30) -> list[dict]:
    horizon = as_of + datetime.timedelta(days=within_days)
    names = {e.id: e.name for e in _user_entities(db, user)}
    if not names:
        return []

    def alert(entity_id, kind, title, due):
        return {
            "entity_id": entity_id,
            "entity_name": names[entity_id],
            "kind": kind,
            "title": title,
            "due_date": due,
            "overdue": due < as_of,
        }

    obligations = (
        db.query(ComplianceObligation)
        .filter(ComplianceObligation.entity_id.in_(names))
        .filter(ComplianceObligation.status.in_(list(_OPEN)))
        .filter(ComplianceObligation.due_date <= horizon)
        .all()
    )
    contracts = (
        db.query(Contract)
        .filter(Contract.entity_id.in_(names), Contract.status == ContractStatus.ACTIVE)
        .filter(Contract.renewal_date.isnot(None), Contract.renewal_date <= horizon)
        .all()
    )
    alerts = [
        alert(o.entity_id, "compliance", f"{o.form_code} — {o.title}", o.due_date)
        for o in obligations
    ] + [
        alert(c.entity_id, "contract_renewal", f"Contract renewal — {c.title}", c.renewal_date)
        for c in contracts
    ]
    alerts.sort(key=lambda a: a["due_date"])
    return alerts


def sweep(db: Session, user: User, as_of: datetime.date, within_days: int = 30) -> int:
    """Create an in-app notification per current alert (deduped by title)."""
    alerts = alerts_for_user(db, user, as_of, within_days)
    existing = {n.title for n in db.query(Notification).filter_by(user_id=user.id)}
    created = 0
    for a in alerts:
        title = ("Overdue: " if a["overdue"] else "Due soon: ") + a["title"]
        if title in existing:
            continue
        notifsvc.notify(
            db, user.id, "reminder", title, f"{a['entity_name']} · due {a['due_date'].isoformat()}"
        )
        created += 1
    return created

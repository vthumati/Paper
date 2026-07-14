"""Rights-issue service (FR-C-7). Entitlements are pro-rata to current
holdings of the class; on close, recorded subscriptions are issued into the
cap-table ledger."""
import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.captable import (
    IssuanceTransaction,
    RightsIssue,
    RightsIssueStatus,
    RightsSubscription,
)
from .captable import compute_cap_table


def _held_by_stakeholder(db: Session, ri: RightsIssue) -> dict[str, int]:
    ct = compute_cap_table(db, ri.entity_id)
    held: dict[str, int] = {}
    for h in ct["holders"]:
        if h["security_class_id"] == ri.security_class_id:
            held[h["stakeholder_id"]] = held.get(h["stakeholder_id"], 0) + h["quantity"]
    return held


def _subscribed_by_stakeholder(db: Session, ri: RightsIssue) -> dict[str, int]:
    subs = db.query(RightsSubscription).filter_by(rights_issue_id=ri.id).all()
    out: dict[str, int] = {}
    for s in subs:
        out[s.stakeholder_id] = out.get(s.stakeholder_id, 0) + s.quantity
    return out


def entitlements(db: Session, ri: RightsIssue) -> dict:
    held = _held_by_stakeholder(db, ri)
    subscribed = _subscribed_by_stakeholder(db, ri)
    from ..models.captable import Stakeholder

    names = {s.id: s.name for s in db.query(Stakeholder).filter_by(entity_id=ri.entity_id)}
    rows = []
    for sh_id, qty in held.items():
        entitled = qty * ri.ratio_num // ri.ratio_den
        rows.append(
            {
                "stakeholder_id": sh_id,
                "stakeholder_name": names.get(sh_id),
                "held": qty,
                "entitled": entitled,
                "subscribed": subscribed.get(sh_id, 0),
            }
        )
    rows.sort(key=lambda r: r["entitled"], reverse=True)
    return {"rights_issue_id": ri.id, "status": ri.status.value, "entitlements": rows}


def subscribe(db: Session, ri: RightsIssue, stakeholder_id: str, quantity: int) -> RightsSubscription:
    if ri.status != RightsIssueStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Rights issue is closed")
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Quantity must be positive")
    held = _held_by_stakeholder(db, ri).get(stakeholder_id, 0)
    entitled = held * ri.ratio_num // ri.ratio_den
    already = _subscribed_by_stakeholder(db, ri).get(stakeholder_id, 0)
    if already + quantity > entitled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Exceeds entitlement (entitled {entitled}, already {already})",
        )
    sub = RightsSubscription(rights_issue_id=ri.id, stakeholder_id=stakeholder_id, quantity=quantity)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def close(db: Session, ri: RightsIssue, as_of: datetime.date) -> dict:
    if ri.status != RightsIssueStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Rights issue is already closed")
    subs = db.query(RightsSubscription).filter_by(rights_issue_id=ri.id).all()
    issued = 0
    raised = Decimal("0")
    for s in subs:
        if s.quantity <= 0:
            continue
        db.add(
            IssuanceTransaction(
                entity_id=ri.entity_id,
                security_class_id=ri.security_class_id,
                stakeholder_id=s.stakeholder_id,
                quantity=s.quantity,
                price_per_unit=ri.price_per_unit,
                issue_date=as_of,
            )
        )
        issued += s.quantity
        raised += Decimal(s.quantity) * Decimal(ri.price_per_unit)
    ri.status = RightsIssueStatus.CLOSED
    db.commit()
    return {"issued_shares": issued, "amount_raised": str(raised)}

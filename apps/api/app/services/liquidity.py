"""Company liquidity windows (FR-C-13): a buyback/tender event that holders
tender shares into; settlement turns each accepted tender into a cap-table
buyback at the event price."""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.captable import BuybackTransaction
from ..models.liquidity import (
    LiquidityEvent,
    LiquidityEventStatus,
    Tender,
    TenderStatus,
)
from .captable import holding_quantity
from .money import CENTS, q


def tender_shares(
    db: Session, event: LiquidityEvent, stakeholder_id: str, security_class_id: str, quantity: int
) -> Tender:
    if event.status != LiquidityEventStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "The liquidity event is not open")
    today = today_ist()
    if not (event.opens_on <= today <= event.closes_on):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The tender window is not currently open")
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quantity must be positive")
    held = holding_quantity(db, event.entity_id, stakeholder_id, security_class_id)
    already = sum(
        t.quantity
        for t in db.query(Tender).filter_by(
            event_id=event.id, stakeholder_id=stakeholder_id,
            security_class_id=security_class_id, status=TenderStatus.SUBMITTED,
        )
    )
    if quantity > held - already:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"You can tender at most {max(0, held - already)} more share(s) of this class",
        )
    t = Tender(
        event_id=event.id,
        entity_id=event.entity_id,
        stakeholder_id=stakeholder_id,
        security_class_id=security_class_id,
        quantity=quantity,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def settle_event(db: Session, event: LiquidityEvent) -> dict:
    """Buy back every submitted tender at the event price (append cap-table
    buybacks), skipping any whose holder no longer has the shares."""
    if event.status != LiquidityEventStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "The event is already settled or cancelled")
    price = Decimal(event.price_per_share)
    settled = 0
    total_shares = 0
    total_amount = Decimal("0")
    for t in db.query(Tender).filter_by(event_id=event.id, status=TenderStatus.SUBMITTED):
        held = holding_quantity(db, event.entity_id, t.stakeholder_id, t.security_class_id)
        if t.quantity > held:
            continue  # holder no longer has the shares — skip, leave submitted
        buyback = BuybackTransaction(
            entity_id=event.entity_id,
            security_class_id=t.security_class_id,
            stakeholder_id=t.stakeholder_id,
            quantity=t.quantity,
            price_per_unit=price,
            date=today_ist(),
        )
        db.add(buyback)
        db.flush()
        t.status = TenderStatus.SETTLED
        t.buyback_id = buyback.id
        settled += 1
        total_shares += t.quantity
        total_amount += price * t.quantity
    event.status = LiquidityEventStatus.SETTLED
    db.commit()
    return {
        "event_id": event.id,
        "tenders_settled": settled,
        "shares_bought_back": total_shares,
        "total_paid": str(q(total_amount)),
    }


def event_view(db: Session, event: LiquidityEvent) -> dict:
    tenders = db.query(Tender).filter_by(event_id=event.id).all()
    tendered = sum(t.quantity for t in tenders if t.status != TenderStatus.WITHDRAWN)
    return {
        "id": event.id,
        "name": event.name,
        "kind": event.kind,
        "price_per_share": str(event.price_per_share),
        "opens_on": event.opens_on.isoformat(),
        "closes_on": event.closes_on.isoformat(),
        "status": event.status.value,
        "tenders": len([t for t in tenders if t.status != TenderStatus.WITHDRAWN]),
        "shares_tendered": tendered,
        "indicative_payout": str((Decimal(event.price_per_share) * tendered).quantize(CENTS)),
    }

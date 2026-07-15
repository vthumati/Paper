"""ESOP service (FR-D): vesting computation and exercise. Exercising options
issues real shares via the cap-table ledger (so exercised options appear in
the cap table) and records the perquisite value for tax."""
import calendar
import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..deps import get_owned
from ..models.captable import IssuanceTransaction, SecurityClass, Stakeholder
from ..models.esop import ESOPScheme, ExerciseTransaction, Grant
from . import valuation as valsvc


def months_between(start: datetime.date, end: datetime.date) -> int:
    if end < start:
        return 0
    m = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
        m -= 1
    return max(0, m)


def vested_quantity(grant: Grant, as_of: datetime.date) -> int:
    m = months_between(grant.grant_date, as_of)
    if m < grant.cliff_months:
        return 0
    if m >= grant.total_months:
        return grant.quantity
    return grant.quantity * m // grant.total_months


def add_months(d: datetime.date, m: int) -> datetime.date:
    y = d.year + (d.month - 1 + m) // 12
    mo = (d.month - 1 + m) % 12 + 1
    return datetime.date(y, mo, min(d.day, calendar.monthrange(y, mo)[1]))


def vesting_projection(grant: Grant, as_of: datetime.date, limit: int = 3) -> dict:
    """Forward view of a grant's vesting: full-vest date and the next few
    monthly vest events (the first event after the cliff is the cliff chunk)."""
    events = []
    prev = vested_quantity(grant, as_of)
    for m in range(1, grant.total_months + 1):
        d = add_months(grant.grant_date, m)
        if d <= as_of:
            continue
        v = vested_quantity(grant, d)
        if v > prev:
            events.append({"date": d, "quantity": v - prev})
            prev = v
        if len(events) >= limit:
            break
    return {
        "full_vest_date": add_months(grant.grant_date, grant.total_months),
        "next_vests": events,
    }


def exercised_quantity(db: Session, grant_id: str) -> int:
    return sum(
        e.quantity for e in db.query(ExerciseTransaction).filter_by(grant_id=grant_id)
    )


def exercised_by_grant(db: Session, entity_id: str) -> dict[str, int]:
    """{grant_id: total exercised} in one grouped query (avoids per-grant N+1)."""
    rows = (
        db.query(ExerciseTransaction.grant_id, func.sum(ExerciseTransaction.quantity))
        .filter_by(entity_id=entity_id)
        .group_by(ExerciseTransaction.grant_id)
        .all()
    )
    return {gid: int(total) for gid, total in rows}


def grant_view(db: Session, grant: Grant, as_of: datetime.date) -> dict:
    vested = vested_quantity(grant, as_of)
    exercised = exercised_quantity(db, grant.id)
    sh = db.get(Stakeholder, grant.stakeholder_id)
    return {
        "id": grant.id,
        "scheme_id": grant.scheme_id,
        "stakeholder_id": grant.stakeholder_id,
        "stakeholder_name": sh.name if sh else None,
        "quantity": grant.quantity,
        "exercise_price": grant.exercise_price,
        "grant_date": grant.grant_date,
        "cliff_months": grant.cliff_months,
        "total_months": grant.total_months,
        "vested": vested,
        "exercised": exercised,
        "exercisable": vested - exercised,
    }


def create_grant(
    db: Session,
    scheme: ESOPScheme,
    stakeholder_id: str,
    quantity: int,
    exercise_price: Decimal,
    grant_date: datetime.date,
    cliff_months: int,
    total_months: int,
) -> Grant:
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quantity must be positive")
    get_owned(db, Stakeholder, stakeholder_id, scheme.entity_id, "stakeholder")
    used = sum(g.quantity for g in db.query(Grant).filter_by(scheme_id=scheme.id))
    if used + quantity > scheme.pool_size:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Grant exceeds scheme pool size")
    grant = Grant(
        scheme_id=scheme.id,
        entity_id=scheme.entity_id,
        stakeholder_id=stakeholder_id,
        quantity=quantity,
        exercise_price=exercise_price,
        grant_date=grant_date,
        cliff_months=cliff_months,
        total_months=total_months,
    )
    db.add(grant)
    db.commit()
    db.refresh(grant)
    return grant


def exercise(
    db: Session,
    grant: Grant,
    quantity: int,
    security_class_id: str,
    fmv_per_share: Decimal,
    as_of: datetime.date,
    cashless: bool = False,
) -> ExerciseTransaction:
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quantity must be positive")
    get_owned(db, SecurityClass, security_class_id, grant.entity_id, "security class")
    exercisable = vested_quantity(grant, as_of) - exercised_quantity(db, grant.id)
    if quantity > exercisable:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Only {exercisable} options are exercisable"
        )
    # If no FMV supplied, fall back to the entity's current valuation (FR-L).
    fmv = Decimal(fmv_per_share)
    if fmv <= 0:
        looked_up = valsvc.current_fmv(db, grant.entity_id, as_of)
        if looked_up is not None:
            fmv = looked_up

    strike = Decimal(grant.exercise_price)
    # gross `quantity` options are consumed from the grant; cashless withholds
    # shares worth the aggregate strike, so fewer net shares are issued.
    net_shares = quantity
    if cashless:
        if fmv <= strike:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "Cashless exercise needs FMV above the strike price"
            )
        net_shares = int(quantity * (fmv - strike) / fmv)

    issuance = IssuanceTransaction(
        entity_id=grant.entity_id,
        security_class_id=security_class_id,
        stakeholder_id=grant.stakeholder_id,
        quantity=net_shares,
        price_per_unit=Decimal("0") if cashless else strike,
        issue_date=as_of,
    )
    db.add(issuance)
    db.flush()
    perquisite = max(Decimal("0"), fmv - strike) * quantity
    ex = ExerciseTransaction(
        grant_id=grant.id,
        entity_id=grant.entity_id,
        quantity=quantity,
        fmv_per_share=fmv,
        exercise_price=strike,
        perquisite_value=perquisite,
        issuance_id=issuance.id,
        date=as_of,
        net_shares=net_shares,
        cashless=cashless,
    )
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return ex

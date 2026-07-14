"""Founder reverse-vesting. Vesting math mirrors ESOP (cliff then monthly to
total). Unvested shares can be repurchased (bought back) on early departure."""
import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.captable import BuybackTransaction
from ..models.founders import FounderVesting
from .esop import months_between


def vested(fv: FounderVesting, as_of: datetime.date) -> int:
    m = months_between(fv.start_date, as_of)
    if m < fv.cliff_months:
        return 0
    if m >= fv.total_months:
        return fv.total_shares
    return fv.total_shares * m // fv.total_months


def view(fv: FounderVesting, as_of: datetime.date) -> dict:
    v = vested(fv, as_of)
    return {
        "id": fv.id,
        "stakeholder_id": fv.stakeholder_id,
        "security_class_id": fv.security_class_id,
        "total_shares": fv.total_shares,
        "vested": v,
        "unvested": fv.total_shares - v,
        "cliff_months": fv.cliff_months,
        "total_months": fv.total_months,
        "start_date": fv.start_date,
        "repurchased": fv.repurchased,
    }


def repurchase_unvested(db: Session, fv: FounderVesting, as_of: datetime.date) -> dict:
    if fv.repurchased:
        raise HTTPException(status.HTTP_409_CONFLICT, "Unvested shares already repurchased")
    unvested = fv.total_shares - vested(fv, as_of)
    if unvested > 0:
        db.add(
            BuybackTransaction(
                entity_id=fv.entity_id,
                security_class_id=fv.security_class_id,
                stakeholder_id=fv.stakeholder_id,
                quantity=unvested,
                price_per_unit=Decimal("0"),
                date=as_of,
            )
        )
    fv.repurchased = True
    db.commit()
    return {"repurchased_shares": unvested}

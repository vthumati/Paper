"""SPV service (FR-S). The sweep creates a single ENTITY-stakeholder holding
in the portfolio company's cap table via the existing issuance ledger."""
import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.captable import (
    IssuanceTransaction,
    SecurityClass,
    Stakeholder,
    StakeholderType,
)
from ..models.spv import CoInvestor, SPV, SPVInvestment


def summary(db: Session, spv: SPV) -> dict:
    cis = db.query(CoInvestor).filter_by(spv_id=spv.id).all()
    committed = sum((Decimal(c.commitment) for c in cis), Decimal("0"))
    contributed = sum((Decimal(c.contributed) for c in cis), Decimal("0"))
    return {
        "spv_id": spv.id,
        "co_investor_count": len(cis),
        "committed": str(committed),
        "contributed": str(contributed),
    }


def contribute(db: Session, ci: CoInvestor) -> CoInvestor:
    if not ci.paid:
        ci.paid = True
        ci.contributed = ci.commitment
        db.commit()
        db.refresh(ci)
    return ci


def invest_in_portco(
    db: Session,
    spv: SPV,
    security_class_id: str,
    quantity: int,
    price_per_unit: Decimal,
    as_of: datetime.date,
) -> SPVInvestment:
    if not spv.portco_entity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "SPV has no portfolio company set")
    if quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "quantity must be positive")
    sc = db.get(SecurityClass, security_class_id)
    if sc is None or sc.entity_id != spv.portco_entity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown security class for the portco")

    # find or create the SPV's stakeholder record in the portco cap table
    sh_name = f"SPV: {spv.target_company}"
    sh = (
        db.query(Stakeholder)
        .filter_by(entity_id=spv.portco_entity_id, name=sh_name)
        .first()
    )
    if sh is None:
        sh = Stakeholder(
            entity_id=spv.portco_entity_id, name=sh_name, type=StakeholderType.ENTITY
        )
        db.add(sh)
        db.flush()

    issuance = IssuanceTransaction(
        entity_id=spv.portco_entity_id,
        security_class_id=security_class_id,
        stakeholder_id=sh.id,
        quantity=quantity,
        price_per_unit=price_per_unit,
        issue_date=as_of,
    )
    db.add(issuance)
    db.flush()
    inv = SPVInvestment(
        spv_id=spv.id,
        portco_entity_id=spv.portco_entity_id,
        security_class_id=security_class_id,
        stakeholder_id=sh.id,
        quantity=quantity,
        price_per_unit=price_per_unit,
        issuance_id=issuance.id,
        date=as_of,
    )
    db.add(inv)
    db.commit()
    db.refresh(inv)
    return inv

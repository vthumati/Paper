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
from ..clock import today_ist
from ..models.entity import LegalEntity
from ..models.fund import Fund, SebiCategory
from ..models.spv import CoInvestor, SPV, SPVInvestment
from . import document as docsvc


def summary(db: Session, spv: SPV) -> dict:
    cis = db.query(CoInvestor).filter_by(spv_id=spv.id).all()
    committed = sum((Decimal(c.commitment) for c in cis), Decimal("0"))
    contributed = sum((Decimal(c.contributed) for c in cis), Decimal("0"))
    by_status = {s: sum(1 for c in cis if c.status == s) for s in ("invited", "committed", "funded")}
    return {
        "spv_id": spv.id,
        "co_investor_count": len(cis),
        "committed": str(committed),
        "contributed": str(contributed),
        "by_status": by_status,
    }


def set_terms(db: Session, spv: SPV, carry_pct: Decimal, min_ticket: Decimal, user_id: str) -> SPV:
    """Store deal economics and provision the fund profile on the SPV entity
    (FR-S-4) so the existing distribution/carry machinery applies. SPVs take
    no hurdle or management fee by default (deal-by-deal carry only)."""
    spv.carry_pct = carry_pct
    spv.min_ticket = min_ticket
    fund = db.query(Fund).filter_by(entity_id=spv.entity_id).first()
    if fund is None:
        fund = Fund(
            entity_id=spv.entity_id,
            sebi_category=SebiCategory.CAT_II,
            structure=spv.structure,
            carry_pct=carry_pct,
            hurdle_pct=Decimal("0"),
            mgmt_fee_pct=Decimal("0"),
            created_by=user_id,
        )
        db.add(fund)
    else:
        fund.carry_pct = carry_pct
    db.commit()
    db.refresh(spv)
    return spv


def contribute(db: Session, ci: CoInvestor) -> CoInvestor:
    if not ci.paid:
        ci.paid = True
        ci.contributed = ci.commitment
        ci.status = "funded"
        db.commit()
        db.refresh(ci)
    return ci


def subscription_agreement(db: Session, spv: SPV, ci: CoInvestor, user_id: str):
    """Generate (or regenerate) the backer's subscription agreement (FR-S-1).
    One document per co-investor; a revised commitment adds a new version."""
    entity = db.get(LegalEntity, spv.entity_id)
    existing = (
        db.query(docsvc.Document)
        .filter_by(subject_type="co_investor", subject_id=ci.id,
                   template_key="subscription_agreement")
        .first()
    )
    data = {
        "vehicle": entity.name if entity else "",
        "target": spv.target_company,
        "sponsor": spv.sponsor,
        "investor": ci.name,
        "amount": str(ci.commitment),
        "carry": str(Decimal(spv.carry_pct) * 100),
        "min_ticket": str(spv.min_ticket),
        "date": today_ist().isoformat(),
    }
    # a signed agreement is immutable — a revised commitment gets a fresh doc
    if existing is not None and existing.status != docsvc.DocumentStatus.SIGNED:
        return docsvc.regenerate(db, existing, data, user_id)
    return docsvc.create_document(
        db, entity_id=spv.entity_id, template_key="subscription_agreement",
        data=data, user_id=user_id,
        title=f"Subscription Agreement — {ci.name}",
        subject_type="co_investor", subject_id=ci.id,
    )


def commit_to_spv(db: Session, ci: CoInvestor, amount: Decimal, user_id: str) -> CoInvestor:
    """A backer commits (or revises a commitment) from the portal (FR-S-3)."""
    if ci.status == "funded":
        raise HTTPException(status.HTTP_409_CONFLICT, "Commitment is already funded")
    spv = db.get(SPV, ci.spv_id)
    if spv.min_ticket and amount < Decimal(spv.min_ticket):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Minimum ticket for this deal is {spv.min_ticket}"
        )
    ci.commitment = amount
    ci.status = "committed"
    subscription_agreement(db, spv, ci, user_id)
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

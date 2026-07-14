"""Fundraising round service (FR-E). Round modelling (pre/post money,
dilution) and closing — which converts outstanding SAFEs/notes, issues funded
commitments into the cap-table ledger, and flags an FC-GPR FEMA filing if any
investor is non-resident."""
import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.captable import IssuanceTransaction, SecurityClass, Stakeholder, StakeholderType
from ..models.compliance import ComplianceObligation, ObligationStatus
from ..models.instruments import ConvertibleInstrument, InstrumentStatus
from ..models.round import Commitment, CommitmentStatus, Round, RoundStatus
from .captable import compute_cap_table
from .compliance import add_obligation
from .instruments import convert as convert_instrument


def round_summary(db: Session, rnd: Round) -> dict:
    commits = db.query(Commitment).filter_by(round_id=rnd.id).all()
    committed = sum((Decimal(c.amount) for c in commits), Decimal("0"))
    pre = Decimal(rnd.pre_money)
    pps = Decimal(rnd.price_per_share)
    existing = compute_cap_table(db, rnd.entity_id)["total_shares"]
    new_shares = int(committed / pps) if pps > 0 else 0
    post_shares = existing + new_shares
    new_own = round(new_shares / post_shares * 100, 4) if post_shares else 0.0
    return {
        "round_id": rnd.id,
        "status": rnd.status.value,
        "instrument": rnd.instrument.value,
        "pre_money": str(pre),
        "target_amount": str(Decimal(rnd.target_amount)),
        "committed": str(committed),
        "post_money": str(pre + committed),
        "price_per_share": str(pps),
        "existing_shares": existing,
        "new_shares": new_shares,
        "implied_new_ownership_pct": new_own,
        "commitment_count": len(commits),
    }


def close_round(db: Session, rnd: Round, as_of: datetime.date) -> dict:
    if rnd.status == RoundStatus.CLOSED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Round is already closed")
    if not rnd.security_class_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Set a security class before closing")
    if Decimal(rnd.price_per_share) <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Set a positive price per share")
    sc = db.get(SecurityClass, rnd.security_class_id)
    if sc is None or sc.entity_id != rnd.entity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Security class not in this entity")

    pps = Decimal(rnd.price_per_share)

    # SAFEs/notes convert automatically at the priced round (FR-C-3), before
    # the round allotments so any valuation cap prices off the pre-financing
    # cap table. An instrument that can't convert (e.g. below one share) is
    # left outstanding rather than blocking the close.
    converted = 0
    for inst in db.query(ConvertibleInstrument).filter_by(
        entity_id=rnd.entity_id, status=InstrumentStatus.OUTSTANDING
    ):
        try:
            convert_instrument(db, inst, pps, rnd.security_class_id, as_of)
            converted += 1
        except HTTPException:
            continue

    funded = [
        c for c in db.query(Commitment).filter_by(round_id=rnd.id, status=CommitmentStatus.FUNDED)
    ]
    issued = 0
    foreign = False
    for c in funded:
        shares = c.shares if c.shares else int(Decimal(c.amount) / pps)
        if shares <= 0:
            continue
        sh = (
            db.query(Stakeholder)
            .filter_by(entity_id=rnd.entity_id, name=c.investor_name)
            .first()
        )
        if sh is None:
            sh = Stakeholder(
                entity_id=rnd.entity_id,
                name=c.investor_name,
                type=StakeholderType.INVESTOR,
                email=c.investor_email,
            )
            db.add(sh)
            db.flush()
        db.add(
            IssuanceTransaction(
                entity_id=rnd.entity_id,
                security_class_id=rnd.security_class_id,
                stakeholder_id=sh.id,
                quantity=shares,
                price_per_unit=pps,
                issue_date=as_of,
            )
        )
        c.stakeholder_id = sh.id
        issued += 1
        if c.is_foreign:
            foreign = True

    rnd.status = RoundStatus.CLOSED

    # event-based filing: PAS-3 (return of allotment) due within 30 days
    if issued > 0:
        add_obligation(
            db,
            rnd.entity_id,
            form_code="PAS-3",
            title=f"Return of allotment (PAS-3) — {rnd.name}",
            category="ROC",
            due_date=as_of + datetime.timedelta(days=30),
            period_label=f"Round-{rnd.id[:8]}",
        )

    fema_obligation = None
    if foreign:
        # FC-GPR is due within 30 days of allotment (FR-H-3)
        ob = ComplianceObligation(
            entity_id=rnd.entity_id,
            form_code="FC-GPR",
            title=f"FC-GPR filing (foreign investment — {rnd.name})",
            category="FEMA",
            period_label=rnd.name,
            due_date=as_of + datetime.timedelta(days=30),
            status=ObligationStatus.DUE,
        )
        db.add(ob)
        db.flush()
        fema_obligation = ob.id

    db.commit()
    return {
        "issued": issued,
        "instruments_converted": converted,
        "foreign_investors": foreign,
        "fc_gpr_obligation_id": fema_obligation,
    }

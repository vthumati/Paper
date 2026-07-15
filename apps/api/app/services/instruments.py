"""Convertible instrument (SAFE / note) conversion. Conversion price is the
lower of the valuation-cap price (cap / current fully-diluted shares) and the
discounted round price; notes add simple accrued interest to the principal."""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..deps import get_owned
from ..models.captable import IssuanceTransaction, SecurityClass, Stakeholder, StakeholderType
from ..models.instruments import ConvertibleInstrument, InstrumentStatus
from .captable import compute_cap_table

from .money import CENTS, PRICE4 as PRICE  # shared quantisation constants


def generate_agreement(db: Session, inst: ConvertibleInstrument, user_id: str):
    """Generate (or re-version) the instrument's agreement document (FR-E-4)."""
    from ..clock import today_ist
    from ..models.entity import LegalEntity
    from . import document as docsvc

    entity = db.get(LegalEntity, inst.entity_id)
    label = "SAFE" if inst.instrument_type.value == "safe" else "CONVERTIBLE NOTE"
    data = {
        "instrument_label": label,
        "company": entity.name if entity else "",
        "investor": inst.investor_name,
        "date": today_ist().isoformat(),
        "principal": str(inst.principal),
        "cap": f"INR {inst.valuation_cap}" if inst.valuation_cap else "uncapped",
        "discount": f"{Decimal(inst.discount_pct) * 100:.0f}%" if inst.discount_pct else "none",
        "mfn": "yes" if inst.mfn else "no",
        "interest": f"{Decimal(inst.interest_pct) * 100:.1f}% p.a." if inst.interest_pct else "none",
    }
    doc = db.get(docsvc.Document, inst.agreement_document_id) if inst.agreement_document_id else None
    if doc is not None and doc.status != docsvc.DocumentStatus.SIGNED:
        doc = docsvc.regenerate(db, doc, data, user_id)
    else:
        doc = docsvc.create_document(
            db, entity_id=inst.entity_id, template_key="safe_agreement", data=data,
            user_id=user_id, title=f"{label.title()} — {inst.investor_name}",
            subject_type="instrument", subject_id=inst.id,
        )
        inst.agreement_document_id = doc.id
        db.commit()
    return doc


def request_board_approval(db: Session, inst: ConvertibleInstrument):
    """Draft the circular board resolution approving this issuance (FR-E-4)."""
    from ..models.governance import Resolution, ResolutionType

    if inst.board_resolution_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Board approval already requested")
    label = "SAFE" if inst.instrument_type.value == "safe" else "convertible note"
    res = Resolution(
        entity_id=inst.entity_id,
        type=ResolutionType.CIRCULAR,
        title=f"Approve {label} issuance — {inst.investor_name} (INR {inst.principal})",
        text=(
            f"RESOLVED THAT the issuance of a {label} of INR {inst.principal} to "
            f"{inst.investor_name} on the terms placed before the board be and is "
            "hereby approved."
        ),
    )
    db.add(res)
    db.flush()
    inst.board_resolution_id = res.id
    db.commit()
    db.refresh(res)
    return res


def execution_status(db: Session, instruments: list[ConvertibleInstrument]) -> dict:
    """{instrument_id: {board, agreement, signature}} for the status dashboard."""
    from ..models.document import Document, SignatureRequest
    from ..models.governance import Resolution

    out = {}
    for inst in instruments:
        board = agreement = signature = None
        if inst.board_resolution_id:
            res = db.get(Resolution, inst.board_resolution_id)
            board = res.status.value if res else None
        if inst.agreement_document_id:
            doc = db.get(Document, inst.agreement_document_id)
            if doc:
                agreement = doc.status.value
                sig = (
                    db.query(SignatureRequest)
                    .filter_by(document_id=doc.id)
                    .order_by(SignatureRequest.created_at.desc())
                    .first()
                )
                signature = sig.status.value if sig else None
        out[inst.id] = {"board": board, "agreement": agreement, "signature": signature}
    return out


def conversion_preview(
    db: Session,
    inst: ConvertibleInstrument,
    round_price: Decimal,
    as_of: datetime.date,
    total_shares: int | None = None,
) -> dict:
    """total_shares (issued) may be passed by callers that already computed the
    cap table — it prices the valuation cap without another ledger replay."""
    principal = Decimal(inst.principal)
    interest = Decimal("0")
    if inst.interest_pct and inst.interest_pct > 0:
        years = Decimal((as_of - inst.issue_date).days) / Decimal("365.25")
        interest = (principal * Decimal(inst.interest_pct) * years).quantize(CENTS, ROUND_HALF_UP)
    amount = principal + interest

    rp = Decimal(round_price)
    candidates = []
    if inst.discount_pct and inst.discount_pct > 0:
        candidates.append(rp * (Decimal("1") - Decimal(inst.discount_pct)))
    if inst.valuation_cap:
        total = (
            total_shares
            if total_shares is not None
            else compute_cap_table(db, inst.entity_id)["total_shares"]
        )
        if total > 0:
            candidates.append(Decimal(inst.valuation_cap) / Decimal(total))
    conv_price = min(candidates) if candidates else rp
    if conv_price <= 0:
        conv_price = rp
    conv_price = conv_price.quantize(PRICE, ROUND_HALF_UP)
    shares = int(amount / conv_price) if conv_price > 0 else 0
    return {
        "amount": str(amount.quantize(CENTS, ROUND_HALF_UP)),
        "accrued_interest": str(interest),
        "conversion_price": str(conv_price),
        "round_price": str(rp),
        "shares": shares,
    }


def convert(
    db: Session,
    inst: ConvertibleInstrument,
    round_price: Decimal,
    security_class_id: str,
    as_of: datetime.date,
) -> dict:
    if inst.status != InstrumentStatus.OUTSTANDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Instrument is not outstanding")
    get_owned(db, SecurityClass, security_class_id, inst.entity_id, "security class")
    preview = conversion_preview(db, inst, round_price, as_of)
    shares = preview["shares"]
    if shares <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Conversion yields zero shares")

    sh = (
        db.query(Stakeholder)
        .filter_by(entity_id=inst.entity_id, name=inst.investor_name)
        .first()
    )
    if sh is None:
        sh = Stakeholder(
            entity_id=inst.entity_id,
            name=inst.investor_name,
            type=StakeholderType.INVESTOR,
            email=inst.investor_email,
        )
        db.add(sh)
        db.flush()
    db.add(
        IssuanceTransaction(
            entity_id=inst.entity_id,
            security_class_id=security_class_id,
            stakeholder_id=sh.id,
            quantity=shares,
            price_per_unit=Decimal(preview["conversion_price"]),
            issue_date=as_of,
        )
    )
    inst.status = InstrumentStatus.CONVERTED
    inst.converted_shares = shares
    inst.stakeholder_id = sh.id
    db.commit()
    return {"converted_shares": shares, "conversion_price": preview["conversion_price"]}

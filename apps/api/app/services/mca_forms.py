"""MCA / RBI statutory form pre-fillers (FR-H): extract data from the equity
ledger and governance records to pre-populate the forms a filing needs —
PAS-3 (allotment), SH-7 (capital increase), MGT-14 (resolution) and FC-GPR
(foreign investment). Structured-summary drafts, rendered to PDF like the rest
of the document module; the user reviews and files on the MCA/FIRMS portals."""
import datetime
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.captable import IssuanceTransaction, SecurityClass, Stakeholder
from ..models.entity import Incorporation, LegalEntity
from ..models.governance import Resolution
from . import document as docsvc
from .captable import compute_cap_table
from .compliance import add_obligation
from .money import q

# Single Master Form (FIRMS) filing steps for an FC-GPR — the checklist an
# Indian company works through to report a foreign issue of shares to the RBI.
SMF_CHECKLIST = [
    "Register the Business User (BU) on the RBI FIRMS portal",
    "Obtain the FIRC and KYC report from the AD Category-I bank",
    "Obtain a valuation certificate (CA/merchant banker, FEMA pricing guidelines)",
    "Enter allottee, instrument and remittance details in the Single Master Form",
    "Attach the board resolution, FIRC, KYC and valuation certificate",
    "Submit FC-GPR within 30 days of allotment and record the acknowledgement",
]


def _cin(entity: LegalEntity) -> str:
    return entity.cin or "(CIN pending)"


def authorised_capital_for(db: Session, entity: LegalEntity) -> Decimal | None:
    """The entity's current authorised capital — from the live entity, falling
    back to its incorporation record."""
    if entity.authorised_capital is not None:
        return Decimal(entity.authorised_capital)
    inc = db.query(Incorporation).filter_by(entity_id=entity.id).first()
    return Decimal(inc.authorised_capital) if inc and inc.authorised_capital is not None else None


def _subject(obligation_id: str | None) -> tuple[str, str | None]:
    return ("compliance", obligation_id) if obligation_id else ("mca_form", None)


def prefill_pas3(
    db: Session, entity: LegalEntity, user_id: str,
    since: datetime.date | None = None, obligation_id: str | None = None,
):
    """PAS-3 return of allotment, pre-filled from the issuance ledger."""
    classes = {c.id: c for c in db.query(SecurityClass).filter_by(entity_id=entity.id)}
    holders = {s.id: s for s in db.query(Stakeholder).filter_by(entity_id=entity.id)}
    q_issue = db.query(IssuanceTransaction).filter_by(entity_id=entity.id)
    if since:
        q_issue = q_issue.filter(IssuanceTransaction.issue_date >= since)
    issues = sorted(q_issue.all(), key=lambda i: i.issue_date)
    lines, total_shares, total_consideration = [], 0, Decimal("0")
    for i in issues:
        sh = holders.get(i.stakeholder_id)
        cls = classes.get(i.security_class_id)
        consideration = Decimal(i.quantity) * Decimal(i.price_per_unit)
        total_shares += i.quantity
        total_consideration += consideration
        lines.append(
            f"  {sh.name if sh else '?'}: {i.quantity:,} {cls.name if cls else '?'} "
            f"@ INR {i.price_per_unit} on {i.issue_date.isoformat()} (INR {q(consideration)})"
        )
    auth = authorised_capital_for(db, entity)
    st, sid = _subject(obligation_id)
    return docsvc.create_document(
        db, entity_id=entity.id, template_key="pas3",
        data={
            "company": entity.name, "cin": _cin(entity),
            "period": (f"since {since.isoformat()}" if since else "all allotments to date"),
            "allotments": "\n".join(lines) or "  (no allotments found)",
            "total_shares": f"{total_shares:,}",
            "total_consideration": str(q(total_consideration)),
            "authorised_capital": str(q(auth)) if auth is not None else "(not set)",
        },
        user_id=user_id, title=f"PAS-3 — {entity.name}", subject_type=st, subject_id=sid,
    )


def prefill_sh7(
    db: Session, entity: LegalEntity, user_id: str, new_authorised: Decimal,
    as_of: datetime.date, resolution_id: str | None = None,
):
    """SH-7 for an increase of authorised capital: generates the form, records
    the SH-7 ROC obligation, and updates the entity's authorised capital."""
    current = authorised_capital_for(db, entity) or Decimal("0")
    new_authorised = Decimal(new_authorised)
    if new_authorised <= current:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"New authorised capital must exceed the current INR {q(current)}",
        )
    res = db.get(Resolution, resolution_id) if resolution_id else None
    doc = docsvc.create_document(
        db, entity_id=entity.id, template_key="sh7",
        data={
            "company": entity.name, "cin": _cin(entity), "date": as_of.isoformat(),
            "from_capital": str(q(current)), "to_capital": str(q(new_authorised)),
            "increase": str(q(new_authorised - current)),
            "resolution": (f"ordinary resolution '{res.title}'" if res else "an ordinary resolution"),
            "passed_date": res.passed_date.isoformat() if res and res.passed_date else as_of.isoformat(),
        },
        user_id=user_id, title=f"SH-7 — {entity.name}",
        subject_type="mca_form", subject_id=None,
    )
    add_obligation(
        db, entity.id, form_code="SH-7",
        title="Increase of authorised capital (SH-7)", category="ROC",
        due_date=as_of + datetime.timedelta(days=30),
        period_label=f"SH7-{doc.id[:8]}",
    )
    entity.authorised_capital = new_authorised
    db.commit()
    return doc


def prefill_mgt14(
    db: Session, resolution: Resolution, user_id: str, obligation_id: str | None = None,
):
    """MGT-14 filing of a resolution, pre-filled from the resolution record."""
    entity = db.get(LegalEntity, resolution.entity_id)
    meeting_ref = ""
    if resolution.meeting_id:
        from ..models.governance import Meeting

        m = db.get(Meeting, resolution.meeting_id)
        if m:
            meeting_ref = f"at the {m.type.value.upper()} meeting on {m.date.isoformat()}"
    st, sid = _subject(obligation_id)
    return docsvc.create_document(
        db, entity_id=resolution.entity_id, template_key="mgt14",
        data={
            "company": entity.name if entity else "", "cin": _cin(entity) if entity else "",
            "title": resolution.title, "res_type": resolution.type.value,
            "passed_date": resolution.passed_date.isoformat() if resolution.passed_date else "(not yet passed)",
            "meeting_ref": meeting_ref, "resolution_text": resolution.text,
        },
        user_id=user_id, title=f"MGT-14 — {resolution.title}",
        subject_type=st, subject_id=sid,
    )


def prefill_fc_gpr(
    db: Session, entity: LegalEntity, user_id: str, obligation_id: str | None = None,
):
    """FC-GPR foreign-investment report, pre-filled from non-resident holders'
    positions in the cap table, plus the SMF filing checklist."""
    non_resident = {
        s.id: s
        for s in db.query(Stakeholder).filter_by(entity_id=entity.id, residency="non_resident")
    }
    lines, total_shares, total_amount = [], 0, Decimal("0")
    if non_resident:
        ct = compute_cap_table(db, entity.id)
        agg: dict[str, dict] = {}
        for h in ct["holders"]:
            if h["stakeholder_id"] in non_resident and h["quantity"] > 0:
                a = agg.setdefault(h["stakeholder_id"], {"qty": 0, "amount": Decimal("0")})
                a["qty"] += h["quantity"]
                a["amount"] += Decimal(h["amount_invested"])
        for sid_, a in agg.items():
            s = non_resident[sid_]
            where = s.country or s.nationality or "non-resident"
            total_shares += a["qty"]
            total_amount += a["amount"]
            lines.append(f"  {s.name} ({where}): {a['qty']:,} shares, INR {q(a['amount'])}")
    checklist = "\n".join(f"  [ ] {step}" for step in SMF_CHECKLIST)
    st, sid = _subject(obligation_id)
    return docsvc.create_document(
        db, entity_id=entity.id, template_key="fc_gpr",
        data={
            "company": entity.name, "cin": _cin(entity),
            "investors": "\n".join(lines) or "  (no non-resident holders on the register)",
            "total_shares": f"{total_shares:,}", "total_amount": str(q(total_amount)),
            "pricing": "FEMA pricing guidelines (Rule 11UA fair value)",
            "checklist": checklist,
        },
        user_id=user_id, title=f"FC-GPR — {entity.name}", subject_type=st, subject_id=sid,
    )


def prefill_for_obligation(db: Session, obligation, user_id: str, resolution_id: str | None = None):
    """Dispatch an auto-created obligation to its form pre-filler (PAS-3, MGT-14,
    FC-GPR). SH-7 is user-initiated (capital increase) and handled separately."""
    entity = db.get(LegalEntity, obligation.entity_id)
    code = obligation.form_code
    if code == "PAS-3":
        return prefill_pas3(db, entity, user_id, obligation_id=obligation.id)
    if code == "FC-GPR":
        return prefill_fc_gpr(db, entity, user_id, obligation_id=obligation.id)
    if code == "MGT-14":
        res = db.get(Resolution, resolution_id) if resolution_id else None
        if res is None:
            # fall back to the latest passed special/circular resolution
            from ..models.governance import ResolutionStatus, ResolutionType

            res = (
                db.query(Resolution)
                .filter_by(entity_id=obligation.entity_id, status=ResolutionStatus.PASSED)
                .filter(Resolution.type.in_([ResolutionType.SPECIAL, ResolutionType.CIRCULAR]))
                .order_by(Resolution.passed_date.desc())
                .first()
            )
        if res is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No passed resolution to file")
        return prefill_mgt14(db, res, user_id, obligation_id=obligation.id)
    raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No pre-filler for {code}")

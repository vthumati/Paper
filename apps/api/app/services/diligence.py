"""Diligence readiness engine (FR-I-5): rules-as-data checks that sweep an
entity's own records for the gaps investors' lawyers look for, producing a
scored report before a data room ever opens. Checks are pure read-side
predicates over existing modules — nothing here writes domain state."""
import datetime

from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.captable import IssuanceTransaction, Stakeholder, StakeholderType
from ..models.compliance import ComplianceObligation, ObligationStatus
from ..models.dataroom import DataRoom, DataRoomAccessGrant
from ..models.document import Document, SignatureRequest, SignatureStatus
from ..models.entity import LegalEntity
from ..models.esop import ESOPScheme, Grant
from ..models.founders import FounderVesting
from ..models.governance import DirectorOfficer, Resolution, ResolutionStatus
from ..models.team import TeamMember
from . import document as docsvc
from .valuation import current_fmv

SEVERITY_WEIGHT = {"high": 15, "medium": 8, "low": 3}

COMPANY_TYPES = ("pvt_ltd", "llp", "opc")


def _finding(code: str, severity: str, title: str, detail: str, tab: str) -> dict:
    return {"code": code, "severity": severity, "title": title, "detail": detail, "tab": tab}


def _check_founder_ip(db: Session, entity_id: str, today) -> list[dict]:
    founders = db.query(Stakeholder).filter_by(
        entity_id=entity_id, type=StakeholderType.FOUNDER
    ).all()
    covered = {
        d.subject_id
        for d in db.query(Document).filter_by(
            entity_id=entity_id, template_key="ip_assignment", subject_type="stakeholder"
        )
    }
    missing = [f.name for f in founders if f.id not in covered]
    if not missing:
        return []
    return [_finding(
        "founder_ip", "high", "Founders without IP assignment",
        f"No IP assignment on record for: {', '.join(missing)}. Founder IP not "
        "owned by the company is the most common diligence red flag.", "documents",
    )]


def _check_founder_vesting(db: Session, entity_id: str, today) -> list[dict]:
    founders = db.query(Stakeholder).filter_by(
        entity_id=entity_id, type=StakeholderType.FOUNDER
    ).all()
    vested = {v.stakeholder_id for v in db.query(FounderVesting).filter_by(entity_id=entity_id)}
    missing = [f.name for f in founders if f.id not in vested]
    if not missing:
        return []
    return [_finding(
        "founder_vesting", "medium", "Founder shares not on reverse vesting",
        f"No vesting schedule for: {', '.join(missing)}. Investors expect founder "
        "shares subject to repurchase on early exit.", "captable",
    )]


def _check_team_ip(db: Session, entity_id: str, today) -> list[dict]:
    members = db.query(TeamMember).filter_by(entity_id=entity_id, status="active").all()
    covered = {
        d.subject_id
        for d in db.query(Document).filter_by(
            entity_id=entity_id, template_key="ip_assignment", subject_type="team_member"
        )
    }
    missing = [m.name for m in members if m.id not in covered]
    if not missing:
        return []
    return [_finding(
        "team_ip", "high", "Team members without IP assignment",
        f"{len(missing)} active team member(s) lack an IP assignment: "
        f"{', '.join(missing[:5])}{'…' if len(missing) > 5 else ''}.", "team",
    )]


def _check_pending_signatures(db: Session, entity_id: str, today) -> list[dict]:
    pending = (
        db.query(SignatureRequest)
        .join(Document, SignatureRequest.document_id == Document.id)
        .filter(Document.entity_id == entity_id,
                SignatureRequest.status == SignatureStatus.PENDING)
        .count()
    )
    if pending == 0:
        return []
    return [_finding(
        "unsigned_docs", "medium", "Documents awaiting signature",
        f"{pending} signature request(s) are still pending — unsigned agreements "
        "are treated as unexecuted in diligence.", "documents",
    )]


def _check_issuances_resolution(db: Session, entity_id: str, today) -> list[dict]:
    has_issuances = db.query(IssuanceTransaction).filter_by(entity_id=entity_id).first()
    if has_issuances is None:
        return []
    passed = db.query(Resolution).filter_by(
        entity_id=entity_id, status=ResolutionStatus.PASSED
    ).first()
    if passed is not None:
        return []
    return [_finding(
        "issuances_no_resolution", "high", "Share issuances without board approval on record",
        "Shares are issued in the ledger but no passed resolution exists. Record "
        "the allotment resolutions that authorised them.", "governance",
    )]


def _check_esop_valuation(db: Session, entity_id: str, today) -> list[dict]:
    has_grants = db.query(Grant).filter_by(entity_id=entity_id).first()
    if has_grants is None or current_fmv(db, entity_id, today) is not None:
        return []
    return [_finding(
        "esop_no_valuation", "high", "ESOP grants without a valuation on record",
        "Options are granted but there is no effective FMV report — exercises and "
        "perquisite tax cannot be priced defensibly.", "valuations",
    )]


def _check_pool_overrun(db: Session, entity_id: str, today) -> list[dict]:
    out = []
    for scheme in db.query(ESOPScheme).filter_by(entity_id=entity_id):
        granted = sum(g.quantity for g in db.query(Grant).filter_by(scheme_id=scheme.id))
        if granted > scheme.pool_size:
            out.append(_finding(
                "pool_overrun", "high", f"ESOP pool over-granted ({scheme.name})",
                f"{granted:,} options granted against a pool of {scheme.pool_size:,}.",
                "esop",
            ))
    return out


def _check_overdue_compliance(db: Session, entity_id: str, today) -> list[dict]:
    overdue = (
        db.query(ComplianceObligation)
        .filter(ComplianceObligation.entity_id == entity_id,
                ComplianceObligation.due_date < today,
                ComplianceObligation.status.in_(
                    [ObligationStatus.DUE, ObligationStatus.IN_PREP]))
        .count()
    )
    if overdue == 0:
        return []
    return [_finding(
        "overdue_compliance", "high", "Overdue statutory filings",
        f"{overdue} obligation(s) are past due. Late ROC/tax filings carry "
        "penalties and surface immediately in diligence.", "compliance",
    )]


def _check_directors(db: Session, entity_id: str, today) -> list[dict]:
    entity = db.get(LegalEntity, entity_id)
    if entity is None or entity.type.value != "pvt_ltd":
        return []
    active = db.query(DirectorOfficer).filter_by(entity_id=entity_id, status="active").count()
    if active >= 2:
        return []
    return [_finding(
        "directors_register", "medium", "Director register below statutory minimum",
        f"Only {active} active director(s) recorded — a private company needs at "
        "least 2 on the register.", "governance",
    )]


def _check_expired_grants(db: Session, entity_id: str, today) -> list[dict]:
    expired = (
        db.query(DataRoomAccessGrant)
        .join(DataRoom, DataRoomAccessGrant.data_room_id == DataRoom.id)
        .filter(DataRoom.entity_id == entity_id,
                DataRoomAccessGrant.expiry.isnot(None),
                DataRoomAccessGrant.expiry < today)
        .count()
    )
    if expired == 0:
        return []
    return [_finding(
        "expired_dataroom_grants", "low", "Expired data-room access grants linger",
        f"{expired} expired grant(s) still listed — remove them to keep the access "
        "register clean.", "documents",
    )]


def _check_stakeholder_emails(db: Session, entity_id: str, today) -> list[dict]:
    missing = (
        db.query(Stakeholder)
        .filter(Stakeholder.entity_id == entity_id, Stakeholder.email.is_(None))
        .count()
    )
    if missing == 0:
        return []
    return [_finding(
        "stakeholder_emails", "low", "Stakeholders without email addresses",
        f"{missing} stakeholder(s) have no email — they cannot receive portal "
        "access, consents or updates.", "captable",
    )]


CHECKS = [
    _check_founder_ip,
    _check_founder_vesting,
    _check_team_ip,
    _check_pending_signatures,
    _check_issuances_resolution,
    _check_esop_valuation,
    _check_pool_overrun,
    _check_overdue_compliance,
    _check_directors,
    _check_expired_grants,
    _check_stakeholder_emails,
]


def run_diligence(db: Session, entity_id: str, as_of: datetime.date | None = None) -> dict:
    today = as_of or today_ist()
    findings: list[dict] = []
    for check in CHECKS:
        findings.extend(check(db, entity_id, today))
    findings.sort(key=lambda f: ("high", "medium", "low").index(f["severity"]))
    score = max(0, 100 - sum(SEVERITY_WEIGHT[f["severity"]] for f in findings))
    return {
        "entity_id": entity_id,
        "as_of": today,
        "score": score,
        "checks_run": len(CHECKS),
        "findings": findings,
        "counts": {s: sum(1 for f in findings if f["severity"] == s)
                   for s in ("high", "medium", "low")},
    }


def generate_report(db: Session, entity_id: str, user_id: str) -> Document:
    result = run_diligence(db, entity_id)
    entity = db.get(LegalEntity, entity_id)
    lines = [
        f"[{f['severity'].upper()}] {f['title']}\n    {f['detail']}"
        for f in result["findings"]
    ] or ["No findings — the record is diligence-ready."]
    return docsvc.create_document(
        db,
        entity_id=entity_id,
        template_key="diligence_report",
        data={
            "company": entity.name if entity else "",
            "date": result["as_of"].isoformat(),
            "score": result["score"],
            "checks_run": result["checks_run"],
            "finding_count": len(result["findings"]),
            "findings": "\n\n".join(lines) + "\n",
        },
        user_id=user_id,
        title=f"Diligence readiness report — {result['as_of'].isoformat()}",
        subject_type="diligence",
        subject_id=entity_id,
    )

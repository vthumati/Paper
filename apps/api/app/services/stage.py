"""Stage guide (see app/stages.py): auto-check checklist items from real data,
suggest a stage from what the company has actually done, and assemble the
guide payload that drives the frontend (tabs shown, features unlocked,
what-to-do-now checklist)."""

from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.captable import IssuanceTransaction, SecurityClass
from ..models.clm import Contract
from ..models.compliance import ComplianceObligation, ObligationStatus
from ..models.crm import ProspectInvestor
from ..models.dataroom import DataRoom
from ..models.entity import LegalEntity
from ..models.esop import ESOPScheme, Grant
from ..models.finance import FinancialSnapshot
from ..models.founders import FounderVesting
from ..models.governance import (
    DirectorOfficer,
    Meeting,
    Resolution,
    ResolutionStatus,
    ResolutionType,
)
from ..models.instruments import ConvertibleInstrument, DematRecord
from ..models.managed import AdminSubscription, AuditEngagement
from ..models.portal import InvestorAccess, InvestorUpdate
from ..models.registers import Registration, SignificantBeneficialOwner
from ..models.round import Round, RoundStatus
from ..models.startup import RecognitionStatus, StartupRecognition
from ..models.team import TeamMember
from ..models.valuation import ValuationReport
from ..stages import (
    PACK_INFO,
    PACKS,
    STAGE_INFO,
    STAGES,
    features_for,
    pack_for_stage,
    pack_rank,
    stage_rank,
    tabs_for,
)


def _has(db: Session, model, **filters) -> bool:
    return db.query(model.id).filter_by(**filters).first() is not None


def _overdue(db: Session, eid: str) -> int:
    today = today_ist()
    return sum(
        1
        for o in db.query(ComplianceObligation).filter_by(entity_id=eid)
        if o.status not in (ObligationStatus.FILED, ObligationStatus.ACKNOWLEDGED)
        and o.due_date and o.due_date < today
    )


# checklist key -> is it done? (matches keys in app/stages.py)
CHECKS = {
    "incorporated": lambda db, e: e.incorporation_date is not None,
    "founder_shares": lambda db, e: _has(db, IssuanceTransaction, entity_id=e.id),
    "founder_vesting": lambda db, e: _has(db, FounderVesting, entity_id=e.id),
    "directors": lambda db, e: _has(db, DirectorOfficer, entity_id=e.id),
    "esop_pool": lambda db, e: _has(db, ESOPScheme, entity_id=e.id),
    "compliance_calendar": lambda db, e: _has(db, ComplianceObligation, entity_id=e.id),
    "registrations": lambda db, e: _has(db, Registration, entity_id=e.id),
    "dpiit": lambda db, e: _has(
        db, StartupRecognition, entity_id=e.id, status=RecognitionStatus.RECOGNISED
    ),
    "team_onboarded": lambda db, e: _has(db, TeamMember, entity_id=e.id),
    "valuation": lambda db, e: _has(db, ValuationReport, entity_id=e.id),
    "pipeline": lambda db, e: _has(db, ProspectInvestor, entity_id=e.id),
    "instrument": lambda db, e: _has(db, ConvertibleInstrument, entity_id=e.id),
    "round_open": lambda db, e: _has(db, Round, entity_id=e.id),
    "dataroom": lambda db, e: _has(db, DataRoom, entity_id=e.id),
    "finance": lambda db, e: _has(db, FinancialSnapshot, entity_id=e.id),
    "esop_granted": lambda db, e: _has(db, Grant, entity_id=e.id),
    "round_closed": lambda db, e: _has(db, Round, entity_id=e.id, status=RoundStatus.CLOSED),
    "board_meeting": lambda db, e: _has(db, Meeting, entity_id=e.id),
    "special_resolution": lambda db, e: _has(
        db, Resolution, entity_id=e.id, type=ResolutionType.SPECIAL, status=ResolutionStatus.PASSED
    ),
    "anti_dilution": lambda db, e: db.query(SecurityClass.id)
    .filter(SecurityClass.entity_id == e.id, SecurityClass.anti_dilution != "none")
    .first()
    is not None,
    "investor_access": lambda db, e: _has(db, InvestorAccess, entity_id=e.id),
    "investor_update": lambda db, e: _has(db, InvestorUpdate, entity_id=e.id),
    "contracts": lambda db, e: _has(db, Contract, entity_id=e.id),
    "sbo_register": lambda db, e: _has(db, SignificantBeneficialOwner, entity_id=e.id),
    "demat": lambda db, e: _has(db, DematRecord, entity_id=e.id),
    # audits hang off the entity's managed-admin subscription
    "audit": lambda db, e: db.query(AuditEngagement.id)
    .join(AdminSubscription, AuditEngagement.subscription_id == AdminSubscription.id)
    .filter(AdminSubscription.entity_id == e.id)
    .first()
    is not None,
    "registers_complete": lambda db, e: _has(db, SignificantBeneficialOwner, entity_id=e.id)
    and _has(db, Registration, entity_id=e.id),
    "compliance_clean": lambda db, e: _has(db, ComplianceObligation, entity_id=e.id)
    and _overdue(db, e.id) == 0,
}


def suggest_stage(db: Session, entity: LegalEntity) -> str:
    """Infer where the company actually is from its data."""
    if _has(db, DematRecord, entity_id=entity.id):
        return "ipo"
    if _has(db, Round, entity_id=entity.id, status=RoundStatus.CLOSED):
        return "series"
    if _has(db, Round, entity_id=entity.id):
        return "seed"
    if _has(db, ConvertibleInstrument, entity_id=entity.id) or _has(
        db, ProspectInvestor, entity_id=entity.id
    ):
        return "preseed"
    return "inception"


def stage_guide(db: Session, entity: LegalEntity) -> dict:
    stage = entity.stage if entity.stage in STAGES else "inception"
    pack = entity.pack if entity.pack in PACKS else "starter"
    info = STAGE_INFO[stage]
    checklist = [
        {**item, "done": CHECKS[item["key"]](db, entity)} for item in info["checklist"]
    ]
    suggested = suggest_stage(db, entity)
    # a stage implies a pack; suggest an upgrade only if it's a higher tier
    suggested_pack = pack_for_stage(suggested)
    return {
        "entity_id": entity.id,
        "stage": stage,
        "label": info["label"],
        "headline": info["headline"],
        "suggested_stage": suggested if stage_rank(suggested) > stage_rank(stage) else None,
        "stages": [{"key": s, "label": STAGE_INFO[s]["label"]} for s in STAGES],
        "pack": pack,
        "packs": [{"key": p, "label": PACK_INFO[p]["label"], "blurb": PACK_INFO[p]["blurb"]} for p in PACKS],
        "suggested_pack": suggested_pack if pack_rank(suggested_pack) > pack_rank(pack) else None,
        "tabs": tabs_for(pack),
        "features": features_for(pack),
        "checklist": checklist,
        "progress": {"done": sum(1 for c in checklist if c["done"]), "total": len(checklist)},
    }

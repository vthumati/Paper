"""Unified entity dashboard (FR-T-3) — aggregates state across modules into
one home view."""

from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.compliance import ComplianceObligation, ObligationStatus
from ..models.dataroom import DataRoom
from ..models.document import Document
from ..models.entity import LegalEntity
from ..models.esop import ESOPScheme, Grant
from ..models.fund import Fund
from ..models.governance import Meeting, Resolution, ResolutionStatus
from ..models.round import Round, RoundStatus
from .captable import compute_cap_table
from .fund import capital_accounts

_OPEN = {ObligationStatus.DUE, ObligationStatus.IN_PREP}


def entity_dashboard(db: Session, entity: LegalEntity) -> dict:
    eid = entity.id
    today = today_ist()

    ct = compute_cap_table(db, eid)
    rounds = db.query(Round).filter_by(entity_id=eid).all()
    obs = db.query(ComplianceObligation).filter_by(entity_id=eid).all()
    overdue = sum(1 for o in obs if o.status in _OPEN and o.due_date < today)
    grants = db.query(Grant).filter_by(entity_id=eid).all()
    resolutions = db.query(Resolution).filter_by(entity_id=eid).all()

    out = {
        "entity": {"id": eid, "name": entity.name, "type": entity.type.value},
        "cap_table": {
            "total_shares": ct["total_shares"],
            "total_invested": ct["total_invested"],
            "holders": len(ct["holders"]),
        },
        "fundraising": {
            "rounds": len(rounds),
            "open_rounds": sum(1 for r in rounds if r.status != RoundStatus.CLOSED),
        },
        "compliance": {"total": len(obs), "overdue": overdue},
        "esop": {
            "schemes": db.query(ESOPScheme).filter_by(entity_id=eid).count(),
            "options_granted": sum(g.quantity for g in grants),
        },
        "governance": {
            "meetings": db.query(Meeting).filter_by(entity_id=eid).count(),
            "pending_resolutions": sum(
                1 for r in resolutions if r.status == ResolutionStatus.DRAFT
            ),
        },
        "documents": db.query(Document).filter_by(entity_id=eid).count(),
        "data_rooms": db.query(DataRoom).filter_by(entity_id=eid).count(),
    }

    fund = db.query(Fund).filter_by(entity_id=eid).first()
    if fund:
        acc = capital_accounts(db, fund)
        out["fund"] = {
            "committed": acc["totals"]["committed"],
            "drawn": acc["totals"]["drawn"],
            "lps": len(acc["accounts"]),
        }
    return out

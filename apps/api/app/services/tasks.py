"""App-wide task hub (FR-T-4, Mantle-style): aggregates everything actionable
for an entity into one ranked list — pending e-signatures, open employee
exercise requests, overdue compliance obligations, and investor consents still
awaited. Read-only; each item carries the tab to deep-link to."""
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.compliance import ComplianceObligation, ObligationStatus
from ..models.document import Document, SignatureRequest, SignatureStatus
from ..models.esop import ExerciseRequest, ExerciseRequestStatus
from ..models.fund import Deal, DealStage, Fund, LPProspect, LPProspectStage
from ..models.governance import Resolution
from ..models.portal import ConsentStatus, InvestorConsent

# a deal parked in one stage this long is flagged stale (4Degrees-style trigger)
STALE_DEAL_DAYS = 45

_OPEN_OBLIG = {ObligationStatus.DUE, ObligationStatus.IN_PREP}
_RANK = {"red": 0, "amber": 1, "ok": 2}


def entity_tasks(db: Session, entity_id: str) -> dict:
    today = today_ist()
    tasks: list[dict] = []

    pending_sigs = (
        db.query(SignatureRequest)
        .join(Document, SignatureRequest.document_id == Document.id)
        .filter(Document.entity_id == entity_id, SignatureRequest.status == SignatureStatus.PENDING)
        .all()
    )
    for s in pending_sigs:
        tasks.append(
            {
                "kind": "signature",
                "tab": "documents",
                "severity": "amber",
                "title": f"Awaiting signature: {s.document.title}",
                "detail": "A generated document has a pending e-signature request.",
            }
        )

    for r in db.query(ExerciseRequest).filter_by(
        entity_id=entity_id, status=ExerciseRequestStatus.OPEN
    ):
        tasks.append(
            {
                "kind": "exercise",
                "tab": "esop",
                "severity": "amber",
                "title": f"Exercise request: {r.quantity:,} options",
                "detail": "An employee requested an option exercise — approve or reject.",
            }
        )

    for o in db.query(ComplianceObligation).filter_by(entity_id=entity_id):
        if o.status in _OPEN_OBLIG and o.due_date < today:
            tasks.append(
                {
                    "kind": "compliance",
                    "tab": "compliance",
                    "severity": "red",
                    "title": f"Overdue: {o.title}",
                    "detail": f"Was due {o.due_date.isoformat()}.",
                }
            )

    for c in db.query(InvestorConsent).filter_by(
        entity_id=entity_id, status=ConsentStatus.PENDING
    ):
        res = db.get(Resolution, c.resolution_id)
        tasks.append(
            {
                "kind": "consent",
                "tab": "governance",
                "severity": "amber",
                "title": f"Awaiting consent: {res.title if res else 'resolution'}",
                "detail": f"{c.email} has not yet responded.",
            }
        )

    # fund entities: overdue deal / LP-prospect follow-ups and stale deals
    fund = db.query(Fund).filter_by(entity_id=entity_id).first()
    if fund is not None:
        for d in db.query(Deal).filter_by(fund_id=fund.id):
            if d.stage in (DealStage.INVESTED, DealStage.PASSED):
                continue
            if d.next_followup_on is not None and d.next_followup_on < today:
                tasks.append(
                    {
                        "kind": "deal_followup",
                        "tab": "fund",
                        "severity": "red",
                        "title": f"Follow up on {d.company_name}",
                        "detail": f"Was due {d.next_followup_on.isoformat()} — deal pipeline.",
                    }
                )
            stage_since = (d.stage_changed_at or d.created_at).date()
            if (today - stage_since).days > STALE_DEAL_DAYS:
                tasks.append(
                    {
                        "kind": "deal_stale",
                        "tab": "fund",
                        "severity": "amber",
                        "title": f"Stale deal: {d.company_name}",
                        "detail": (
                            f"In '{d.stage.value}' for {(today - stage_since).days} days "
                            f"(over {STALE_DEAL_DAYS}) — move it or pass."
                        ),
                    }
                )
        for p in db.query(LPProspect).filter_by(fund_id=fund.id):
            if (
                p.next_followup_on is not None
                and p.next_followup_on < today
                and p.stage not in (LPProspectStage.COMMITTED, LPProspectStage.PASSED)
            ):
                tasks.append(
                    {
                        "kind": "lp_followup",
                        "tab": "fund",
                        "severity": "red",
                        "title": f"Follow up with {p.name}",
                        "detail": f"Was due {p.next_followup_on.isoformat()} — LP fundraise.",
                    }
                )

    tasks.sort(key=lambda t: _RANK.get(t["severity"], 3))
    return {
        "tasks": tasks,
        "counts": {
            "total": len(tasks),
            "overdue": sum(1 for t in tasks if t["severity"] == "red"),
        },
    }

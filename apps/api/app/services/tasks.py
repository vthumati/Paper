"""App-wide task hub (FR-T-4, Mantle-style): aggregates everything actionable
for an entity into one ranked list — pending e-signatures, open employee
exercise requests, overdue compliance obligations, and investor consents still
awaited. Read-only; each item carries the tab to deep-link to."""
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.compliance import ComplianceObligation, ObligationStatus
from ..models.document import Document, SignatureRequest, SignatureStatus
from ..models.esop import ExerciseRequest, ExerciseRequestStatus
from ..models.fund import Deal, DealStage, Fund
from ..models.governance import Resolution
from ..models.portal import ConsentStatus, InvestorConsent

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

    # overdue deal follow-ups (fund entities): promised touches that slipped
    fund = db.query(Fund).filter_by(entity_id=entity_id).first()
    if fund is not None:
        for d in db.query(Deal).filter_by(fund_id=fund.id):
            if (
                d.next_followup_on is not None
                and d.next_followup_on < today
                and d.stage not in (DealStage.INVESTED, DealStage.PASSED)
            ):
                tasks.append(
                    {
                        "kind": "deal_followup",
                        "tab": "fund",
                        "severity": "red",
                        "title": f"Follow up on {d.company_name}",
                        "detail": f"Was due {d.next_followup_on.isoformat()} — deal pipeline.",
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

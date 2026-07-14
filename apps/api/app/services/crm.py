"""Investor CRM / fundraising pipeline service (FR-E-1). Pipeline summary by
stage, and conversion of a committed prospect into a round commitment."""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.crm import PipelineStage, ProspectInvestor
from ..models.round import Commitment, CommitmentStatus, Round

_OPEN = {
    PipelineStage.CONTACTED,
    PipelineStage.MEETING,
    PipelineStage.DILIGENCE,
    PipelineStage.TERM_SHEET,
}


def pipeline_summary(db: Session, entity_id: str) -> dict:
    prospects = db.query(ProspectInvestor).filter_by(entity_id=entity_id).all()
    by_stage: dict[str, dict] = {}
    open_value = Decimal("0")
    committed_value = Decimal("0")
    for p in prospects:
        s = by_stage.setdefault(p.stage.value, {"count": 0, "value": Decimal("0")})
        s["count"] += 1
        cs = Decimal(p.check_size) if p.check_size is not None else Decimal("0")
        s["value"] += cs
        if p.stage in _OPEN:
            open_value += cs
        elif p.stage == PipelineStage.COMMITTED:
            committed_value += cs
    return {
        "by_stage": {k: {"count": v["count"], "value": str(v["value"])} for k, v in by_stage.items()},
        "open_value": str(open_value),
        "committed_value": str(committed_value),
        "total": len(prospects),
    }


def convert_to_commitment(db: Session, prospect: ProspectInvestor) -> dict:
    if not prospect.round_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Prospect is not linked to a round")
    if prospect.commitment_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Already converted to a commitment")
    rnd = db.get(Round, prospect.round_id)
    if rnd is None or rnd.entity_id != prospect.entity_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Linked round not found for this entity")
    if prospect.check_size is None or prospect.check_size <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Set a check size before converting")
    c = Commitment(
        round_id=rnd.id,
        investor_name=prospect.name,
        investor_email=prospect.email,
        amount=prospect.check_size,
        status=CommitmentStatus.SIGNED,
    )
    db.add(c)
    db.flush()
    prospect.commitment_id = c.id
    prospect.stage = PipelineStage.COMMITTED
    db.commit()
    return {"commitment_id": c.id, "round_id": rnd.id}

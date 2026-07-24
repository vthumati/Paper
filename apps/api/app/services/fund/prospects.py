"""LP-fundraising CRM: raising the fund from prospective LPs."""
from decimal import Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models.fund import LP, Fund, LPProspect, LPProspectStage
from ..money import q

# pipeline stages that count as "still being worked" (not yet won or lost)
_ACTIVE_PROSPECT_STAGES = {
    LPProspectStage.PROSPECT,
    LPProspectStage.CONTACTED,
    LPProspectStage.MEETING,
    LPProspectStage.DILIGENCE,
    LPProspectStage.SOFT_CIRCLED,
}


def add_prospect(db: Session, fund: Fund, data: dict) -> LPProspect:
    p = LPProspect(fund_id=fund.id, **data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def set_prospect_stage(db: Session, prospect: LPProspect, stage: LPProspectStage) -> LPProspect:
    prospect.stage = stage
    db.commit()
    db.refresh(prospect)
    return prospect


def convert_prospect_to_lp(db: Session, prospect: LPProspect, commitment: Decimal | None) -> LP:
    """Turn a won prospect into an LP with a commitment. Idempotent-guarded:
    a prospect already linked to an LP can't be converted twice."""
    if prospect.lp_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Prospect already converted to an LP")
    amount = commitment if commitment is not None else Decimal(prospect.target_commitment)
    lp = LP(fund_id=prospect.fund_id, name=prospect.name, email=prospect.email, commitment=amount)
    db.add(lp)
    db.flush()
    prospect.lp_id = lp.id
    prospect.stage = LPProspectStage.COMMITTED
    db.commit()
    db.refresh(lp)
    return lp


def _prospect_view(p: LPProspect) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "firm": p.firm,
        "kind": p.kind,
        "email": p.email,
        "stage": p.stage.value,
        "target_commitment": str(q(p.target_commitment)),
        "notes": p.notes,
        "lp_id": p.lp_id,
        "next_followup_on": p.next_followup_on,
    }


def fundraise_summary(db: Session, fund: Fund) -> dict:
    """The fund's own raise: prospect pipeline by stage + progress toward the
    target corpus. 'Committed' is the actual committed LP capital; 'soft-circled'
    and 'pipeline' come from the prospect targets."""
    prospects = db.query(LPProspect).filter_by(fund_id=fund.id).all()
    committed = sum(
        (Decimal(lp.commitment) for lp in db.query(LP).filter_by(fund_id=fund.id)), Decimal("0")
    )
    target = Decimal(fund.target_corpus or 0)

    by_stage: dict[str, dict] = {}
    soft_circled = Decimal("0")
    pipeline = Decimal("0")
    for p in prospects:
        row = by_stage.setdefault(p.stage.value, {"count": 0, "target": Decimal("0")})
        row["count"] += 1
        row["target"] += Decimal(p.target_commitment)
        if p.stage == LPProspectStage.SOFT_CIRCLED:
            soft_circled += Decimal(p.target_commitment)
        if p.stage in _ACTIVE_PROSPECT_STAGES:
            pipeline += Decimal(p.target_commitment)

    return {
        "fund_id": fund.id,
        "target_corpus": str(q(target)),
        "committed": str(q(committed)),
        "soft_circled": str(q(soft_circled)),
        "pipeline": str(q(pipeline)),
        "progress_pct": round(float(committed / target * 100), 1) if target > 0 else None,
        "by_stage": {k: {"count": v["count"], "target": str(q(v["target"]))} for k, v in by_stage.items()},
        "prospects": [_prospect_view(p) for p in prospects],
    }

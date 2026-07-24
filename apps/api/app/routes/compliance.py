import datetime

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    ObligationCtx,
    PageCtx,
    entity_ctx,
    get_current_user,
    obligation_ctx,
    page,
    require_write,
)
from ..models.compliance import ComplianceObligation
from ..models.document import Document
from ..models.identity import User
from ..schemas import (
    ComplianceGenerateIn,
    DocumentOut,
    ObligationOut,
    ObligationStatusIn,
    PrefillIn,
)
from ..services import compliance as svc
from ..services import document as docsvc
from ..services import mca_forms as mcasvc
from ..services import notification as notifsvc

router = APIRouter(tags=["compliance"])


@router.post("/entities/{entity_id}/compliance/generate", response_model=list[ObligationOut])
def generate(
    body: ComplianceGenerateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    n = svc.generate_for_fy(db, ctx.entity.id, body.financial_year_end)
    if n:
        notifsvc.notify(
            db,
            user.id,
            "compliance",
            "Compliance calendar generated",
            f"{n} statutory obligation(s) added.",
        )
    return _list(db, ctx.entity.id, today_ist())


@router.post("/entities/{entity_id}/compliance/generate-periodic", response_model=list[ObligationOut])
def generate_periodic(
    body: ComplianceGenerateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    n = svc.generate_periodic(db, ctx.entity.id, body.financial_year_end)
    notifsvc.notify(
        db, user.id, "compliance", "Periodic GST/TDS schedule generated",
        f"{n} recurring obligations on record.",
    )
    return _list(db, ctx.entity.id, today_ist())


@router.post("/entities/{entity_id}/compliance/generate-aif", response_model=list[ObligationOut])
def generate_aif(
    body: ComplianceGenerateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    n = svc.generate_aif(db, ctx.entity.id, body.financial_year_end)
    notifsvc.notify(
        db, user.id, "compliance", "SEBI AIF calendar generated",
        f"{n} SEBI obligations on record.",
    )
    return _list(db, ctx.entity.id, today_ist())


@router.get("/entities/{entity_id}/compliance/health")
def compliance_health(
    as_of: datetime.date | None = None,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    return svc.health_score(db, ctx.entity.id, as_of or today_ist())


@router.get("/entities/{entity_id}/compliance", response_model=list[ObligationOut])
def list_obligations(
    as_of: datetime.date | None = None,
    p: PageCtx = Depends(page),
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    return _list(db, ctx.entity.id, as_of or today_ist(), p.limit, p.offset)


@router.post("/compliance/{obligation_id}/status", response_model=ObligationOut)
def update_status(
    body: ObligationStatusIn,
    ctx: ObligationCtx = Depends(obligation_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    ob = ctx.obligation
    ob.status = body.status
    if body.srn is not None:
        ob.srn = body.srn
    if body.assignee is not None:
        ob.assignee = body.assignee
    db.commit()
    db.refresh(ob)
    return svc.obligation_view(ob, today_ist())


@router.get("/entities/{entity_id}/fema/tracker")
def fema_tracker(
    as_of: datetime.date | None = None,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    """FEMA/RBI cross-border tracker: FEMA obligations (FC-GPR etc.), the
    non-resident holders on the register, and the SMF filing checklist."""
    from ..models.captable import Stakeholder

    ref = as_of or today_ist()
    obs = (
        db.query(ComplianceObligation)
        .filter_by(entity_id=ctx.entity.id, category="FEMA")
        .order_by(ComplianceObligation.due_date)
        .all()
    )
    linked = {}
    if obs:
        linked = {
            d.subject_id: d.id
            for d in db.query(Document).filter(
                Document.subject_type == "compliance",
                Document.subject_id.in_([o.id for o in obs]),
            )
        }
    non_resident = [
        {"id": s.id, "name": s.name, "country": s.country, "nationality": s.nationality}
        for s in db.query(Stakeholder).filter_by(entity_id=ctx.entity.id, residency="non_resident")
    ]
    return {
        "obligations": [
            {**svc.obligation_view(o, ref), "document_id": linked.get(o.id)} for o in obs
        ],
        "non_resident_holders": non_resident,
        "smf_checklist": mcasvc.SMF_CHECKLIST,
    }


@router.post("/compliance/{obligation_id}/prefill", response_model=DocumentOut, status_code=201)
def prefill_form(
    body: PrefillIn,
    ctx: ObligationCtx = Depends(obligation_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Pre-fill the statutory form for an obligation from the ledger (PAS-3,
    MGT-14, FC-GPR) and link the generated draft to the obligation."""
    require_write(ctx.role)
    doc = mcasvc.prefill_for_obligation(db, ctx.obligation, user.id, resolution_id=body.resolution_id)
    return docsvc.document_view(db, doc)


def _list(
    db: Session, entity_id: str, as_of: datetime.date, limit: int = 500, offset: int = 0
) -> list[dict]:
    obs = (
        db.query(ComplianceObligation)
        .filter_by(entity_id=entity_id)
        .order_by(ComplianceObligation.due_date)
        .offset(offset)
        .limit(limit)
        .all()
    )
    # attach any pre-filled form document linked to each obligation
    docs = {}
    if obs:
        docs = {
            d.subject_id: d.id
            for d in db.query(Document).filter(
                Document.subject_type == "compliance",
                Document.subject_id.in_([o.id for o in obs]),
            )
        }
    out = []
    for o in obs:
        v = svc.obligation_view(o, as_of)
        v["document_id"] = docs.get(o.id)
        out.append(v)
    return out

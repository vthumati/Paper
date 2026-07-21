from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import now_ist, today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    SecondaryCtx,
    UpdateCtx,
    entity_ctx,
    get_current_user,
    get_owned,
    require_admin,
    require_verified_email,
    require_write,
    secondary_ctx,
    update_ctx,
)
from ..models.captable import SecurityClass, Stakeholder, TransferTransaction
from ..models.identity import User
from ..models.portal import (
    ConsentStatus,
    InvestorAccess,
    InvestorConsent,
    InvestorUpdate,
    InvestorUpdateView,
    SecondaryRequest,
    SecondaryStatus,
)
from ..schemas import (
    ConsentDecisionIn,
    ExerciseRequestIn,
    KPIRequestSubmitIn,
    InvestorAccessIn,
    InvestorAccessOut,
    InvestorUpdateIn,
    InvestorUpdateOut,
    SecondaryDecideIn,
    SecondaryRequestIn,
    SPVCommitIn,
    TenderIn,
)
from ..services import portal as svc
from ..services.captable import holding_quantity, stamp_duty_on_transfer

router = APIRouter(tags=["portal"])


# --- admin side: grant access + publish updates (entity members) ---
@router.post("/entities/{entity_id}/investor-access", response_model=InvestorAccessOut, status_code=201)
def grant_access(
    body: InvestorAccessIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_admin(ctx.role)
    if body.stakeholder_id:
        sh = db.get(Stakeholder, body.stakeholder_id)
        if sh is None or sh.entity_id != ctx.entity.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown stakeholder for this entity")
    access = InvestorAccess(
        entity_id=ctx.entity.id,
        email=body.email,
        stakeholder_id=body.stakeholder_id,
        status="active",
        created_by=user.id,
    )
    db.add(access)
    db.commit()
    db.refresh(access)
    return access


@router.get("/entities/{entity_id}/investor-access", response_model=list[InvestorAccessOut])
def list_access(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(InvestorAccess).filter_by(entity_id=ctx.entity.id).all()


def _metrics_snapshot(db: Session, entity) -> dict:
    """JSON-safe copy of the live metrics, frozen onto the update at publish."""
    import datetime as _dt
    from decimal import Decimal

    from ..services.reporting import report_metrics

    out = {}
    for k, v in report_metrics(db, entity).items():
        if isinstance(v, Decimal):
            out[k] = str(v)
        elif isinstance(v, (_dt.date, _dt.datetime)):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


@router.post("/entities/{entity_id}/investor-updates", response_model=InvestorUpdateOut, status_code=201)
def publish_update(
    body: InvestorUpdateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    upd = InvestorUpdate(
        entity_id=ctx.entity.id,
        title=body.title,
        body=body.body,
        period_label=body.period_label,
        highlights=body.highlights,
        lowlights=body.lowlights,
        asks=body.asks,
        status="published" if body.publish else "draft",
        created_by=user.id,
    )
    if body.publish:
        upd.metrics = _metrics_snapshot(db, ctx.entity)
        upd.published_at = now_ist()
    db.add(upd)
    db.commit()
    db.refresh(upd)
    return upd


@router.put("/investor-updates/{update_id}", response_model=InvestorUpdateOut)
def edit_update(
    body: InvestorUpdateIn,
    ctx: UpdateCtx = Depends(update_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    upd = ctx.update
    if upd.status != "draft":
        raise HTTPException(status.HTTP_409_CONFLICT, "Only drafts can be edited")
    upd.title = body.title
    upd.body = body.body
    upd.period_label = body.period_label
    upd.highlights = body.highlights
    upd.lowlights = body.lowlights
    upd.asks = body.asks
    db.commit()
    db.refresh(upd)
    return upd


@router.post("/investor-updates/{update_id}/publish", response_model=InvestorUpdateOut)
def publish_draft(ctx: UpdateCtx = Depends(update_ctx), db: Session = Depends(get_db)):
    from ..models.entity import LegalEntity

    require_write(ctx.role)
    upd = ctx.update
    if upd.status == "published":
        raise HTTPException(status.HTTP_409_CONFLICT, "Update is already published")
    upd.status = "published"
    upd.metrics = _metrics_snapshot(db, db.get(LegalEntity, upd.entity_id))
    upd.published_at = now_ist()
    db.commit()
    db.refresh(upd)
    return upd


@router.get("/entities/{entity_id}/investor-updates")
def list_updates(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    updates = (
        db.query(InvestorUpdate)
        .filter_by(entity_id=ctx.entity.id)
        .order_by(InvestorUpdate.created_at.desc())
        .all()
    )
    views = db.query(InvestorUpdateView).filter(
        InvestorUpdateView.update_id.in_([u.id for u in updates])
    ).all() if updates else []
    by_update: dict[str, list] = {}
    for v in views:
        by_update.setdefault(v.update_id, []).append(v)
    return [
        {
            "id": u.id,
            "title": u.title,
            "body": u.body,
            "period_label": u.period_label,
            "highlights": u.highlights,
            "lowlights": u.lowlights,
            "asks": u.asks,
            "metrics": u.metrics,
            "status": u.status,
            "published_at": u.published_at,
            "created_at": u.created_at,
            "viewers": [
                {
                    "email": v.email,
                    "view_count": v.view_count,
                    "last_viewed_at": v.last_viewed_at,
                }
                for v in sorted(by_update.get(u.id, []), key=lambda v: v.email)
            ],
        }
        for u in updates
    ]


# --- investor side: scoped read-only portal (any authenticated user) ---
@router.get("/portal")
def my_portal(user: User = Depends(require_verified_email), db: Session = Depends(get_db)):
    return svc.portal_for_user(db, user)


@router.get("/portal/value-history")
def my_portal_value_history(
    user: User = Depends(require_verified_email), db: Session = Depends(get_db)
):
    return svc.portfolio_value_history(db, user)


@router.post("/portal/kpi-requests/{request_id}/submit")
def submit_kpi_request(
    request_id: str,
    body: KPIRequestSubmitIn,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    """A portfolio-company contact submits KPI values for a requested period."""
    return svc.submit_kpi_request(db, user, request_id, body.model_dump())


@router.post("/portal/updates/{update_id}/view")
def view_update(
    update_id: str,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    """Record that an invited investor opened a published update (engagement)."""
    upd = db.get(InvestorUpdate, update_id)
    access = (
        db.query(InvestorAccess)
        .filter_by(entity_id=upd.entity_id, email=user.email)
        .first()
        if upd is not None
        else None
    )
    if upd is None or upd.status != "published" or access is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Update not found")
    view = (
        db.query(InvestorUpdateView)
        .filter_by(update_id=upd.id, email=user.email)
        .first()
    )
    if view is None:
        view = InvestorUpdateView(update_id=upd.id, email=user.email, view_count=0)
        db.add(view)
    view.view_count += 1
    view.last_viewed_at = now_ist()
    db.commit()
    return {"id": upd.id, "view_count": view.view_count}


@router.get("/portal/funds/{fund_id}/lp-report")
def portal_lp_report(
    fund_id: str,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    """The web-native quarterly report for an LP of the fund (email-scoped),
    for the last completed quarter."""
    from ..clock import today_ist
    from ..models.entity import LegalEntity
    from ..models.fund import LP, Fund
    from ..services import fund as fund_svc

    fund = db.get(Fund, fund_id)
    is_lp = (
        db.query(LP).filter_by(fund_id=fund_id, email=user.email).first() if fund else None
    )
    if fund is None or is_lp is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fund not found")
    entity = db.get(LegalEntity, fund.entity_id)
    label, start, end = fund_svc.default_report_period(today_ist())
    return fund_svc.lp_report_data(
        db, fund, entity.name if entity else "", label, start, end
    )


@router.post("/portal/notices/{notice_id}/ack")
def acknowledge_notice(
    notice_id: str,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    """LP acknowledges a capital-call notice they can see in their portal."""
    return svc.acknowledge_notice(db, user, notice_id)


@router.get("/portal/grants/{grant_id}/detail")
def my_grant_detail(
    grant_id: str,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    detail = svc.grant_detail_for_user(db, user, grant_id)
    if detail is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found")
    return detail


# --- portal PDF: LPs download their own statements / Form 64C by email match ---
@router.get("/portal/documents/{document_id}/pdf")
def portal_document_pdf(
    document_id: str,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    from ..models.document import Document
    from ..models.fund import LP
    from ..models.spv import CoInvestor
    from .documents import document_pdf_response

    doc = db.get(Document, document_id)
    if doc is None or doc.subject_type not in ("lp_statement", "form_64c", "co_investor"):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    if doc.subject_type == "co_investor":
        ci = db.get(CoInvestor, doc.subject_id) if doc.subject_id else None
        if ci is None or ci.email != user.email:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    else:
        lp = db.get(LP, doc.subject_id) if doc.subject_id else None
        if lp is None or lp.email != user.email:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Document not found")
    return document_pdf_response(db, doc)


# --- investor consents: decided by the invited email, not by membership ---
@router.post("/portal/consents/{consent_id}")
def decide_consent(
    consent_id: str,
    body: ConsentDecisionIn,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    consent = db.get(InvestorConsent, consent_id)
    if consent is None or consent.email != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Consent not found")
    if consent.status != ConsentStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Consent is already decided")
    consent.status = ConsentStatus.APPROVED if body.approve else ConsentStatus.REJECTED
    consent.decided_at = now_ist()
    db.commit()
    return {"id": consent.id, "status": consent.status.value}


# --- employee exercise requests: asked here, decided by the company ---
@router.post("/portal/exercise-requests", status_code=201)
def request_exercise(
    body: ExerciseRequestIn,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    from ..models.esop import ExerciseRequest, ExerciseRequestStatus, Grant
    from ..services.esop import exercise_allowed, exercised_quantity, vested_quantity

    grant = db.get(Grant, body.grant_id)
    sh = db.get(Stakeholder, grant.stakeholder_id) if grant else None
    if grant is None or sh is None or sh.email != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found")
    if not exercise_allowed(db, grant.entity_id, today_ist()):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Exercise is only allowed during an open exercise window",
        )
    exercisable = vested_quantity(grant, today_ist()) - exercised_quantity(db, grant.id)
    pending = sum(
        r.quantity
        for r in db.query(ExerciseRequest).filter_by(
            grant_id=grant.id, status=ExerciseRequestStatus.OPEN
        )
    )
    if body.quantity > exercisable - pending:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Only {max(0, exercisable - pending)} option(s) are exercisable",
        )
    req = ExerciseRequest(
        entity_id=grant.entity_id, grant_id=grant.id,
        quantity=body.quantity, cashless=body.cashless,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"id": req.id, "status": req.status.value}


# --- SPV commitments: an invited backer commits to the deal (FR-S-3) ---
@router.post("/portal/spv-commitments")
def commit_to_spv(
    body: SPVCommitIn,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    from ..models.spv import CoInvestor
    from ..services import spv as spv_svc

    ci = db.get(CoInvestor, body.co_investor_id)
    if ci is None or ci.email != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    ci = spv_svc.commit_to_spv(db, ci, body.amount, user.id)
    return {"id": ci.id, "status": ci.status, "commitment": str(ci.commitment)}


# --- liquidity: a holder tenders shares into an open buyback/tender window ---
@router.post("/portal/tenders", status_code=201)
def tender_shares(
    body: TenderIn,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    from ..models.liquidity import LiquidityEvent
    from ..services import liquidity as liq

    ev = db.get(LiquidityEvent, body.event_id)
    if ev is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Liquidity event not found")
    # the tendering holder must be a stakeholder of the entity matched by email
    sh = (
        db.query(Stakeholder)
        .filter_by(entity_id=ev.entity_id, email=user.email)
        .first()
    )
    if sh is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You hold no shares in this company")
    t = liq.tender_shares(db, ev, sh.id, body.security_class_id, body.quantity)
    return {"id": t.id, "status": t.status.value, "quantity": t.quantity}


# --- secondary sales: the investor asks, the company decides (ROFR) ---
@router.post("/portal/secondary-requests", status_code=201)
def request_sale(
    body: SecondaryRequestIn,
    user: User = Depends(require_verified_email),
    db: Session = Depends(get_db),
):
    access = (
        db.query(InvestorAccess)
        .filter_by(entity_id=body.entity_id, email=user.email)
        .filter(InvestorAccess.stakeholder_id.isnot(None))
        .first()
    )
    if access is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "No shareholding linked to your portal access"
        )
    held = holding_quantity(db, body.entity_id, access.stakeholder_id, body.security_class_id)
    if body.quantity <= 0 or body.quantity > held:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"You hold {held} of this class")
    req = SecondaryRequest(
        entity_id=body.entity_id,
        stakeholder_id=access.stakeholder_id,
        security_class_id=body.security_class_id,
        quantity=body.quantity,
        price_per_unit=body.price_per_unit,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return {"id": req.id, "status": req.status.value}


@router.get("/entities/{entity_id}/secondary-requests")
def list_secondary_requests(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    names = {s.id: s.name for s in db.query(Stakeholder).filter_by(entity_id=ctx.entity.id)}
    classes = {c.id: c.name for c in db.query(SecurityClass).filter_by(entity_id=ctx.entity.id)}
    return [
        {
            "id": r.id,
            "seller": names.get(r.stakeholder_id),
            "security_class": classes.get(r.security_class_id),
            "quantity": r.quantity,
            "price_per_unit": str(r.price_per_unit),
            "status": r.status.value,
            "buyer": names.get(r.buyer_stakeholder_id) if r.buyer_stakeholder_id else None,
        }
        for r in db.query(SecondaryRequest).filter_by(entity_id=ctx.entity.id)
    ]


@router.post("/secondary-requests/{request_id}/decide")
def decide_secondary(
    body: SecondaryDecideIn,
    ctx: SecondaryCtx = Depends(secondary_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    req = ctx.request
    if req.status != SecondaryStatus.OPEN:
        raise HTTPException(status.HTTP_409_CONFLICT, "Request is already decided")
    if not body.approve:
        req.status = SecondaryStatus.REJECTED
        db.commit()
        return {"id": req.id, "status": req.status.value}
    if not body.buyer_stakeholder_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Choose a buyer to exercise ROFR")
    get_owned(db, Stakeholder, body.buyer_stakeholder_id, req.entity_id, "stakeholder")
    held = holding_quantity(db, req.entity_id, req.stakeholder_id, req.security_class_id)
    if req.quantity > held:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Seller now holds only {held}")
    txn = TransferTransaction(
        entity_id=req.entity_id,
        security_class_id=req.security_class_id,
        from_stakeholder_id=req.stakeholder_id,
        to_stakeholder_id=body.buyer_stakeholder_id,
        quantity=req.quantity,
        price_per_unit=req.price_per_unit,
        transfer_date=today_ist(),
        stamp_duty=stamp_duty_on_transfer(req.quantity * req.price_per_unit),
    )
    db.add(txn)
    db.flush()
    req.status = SecondaryStatus.EXECUTED
    req.buyer_stakeholder_id = body.buyer_stakeholder_id
    req.transfer_id = txn.id
    db.commit()
    return {"id": req.id, "status": req.status.value, "transfer_id": txn.id}

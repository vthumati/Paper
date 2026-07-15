from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import now_ist, today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    SecondaryCtx,
    entity_ctx,
    get_current_user,
    get_owned,
    require_write,
    secondary_ctx,
)
from ..models.captable import SecurityClass, Stakeholder, TransferTransaction
from ..models.identity import User
from ..models.portal import (
    ConsentStatus,
    InvestorAccess,
    InvestorConsent,
    InvestorUpdate,
    SecondaryRequest,
    SecondaryStatus,
)
from ..schemas import (
    ConsentDecisionIn,
    ExerciseRequestIn,
    InvestorAccessIn,
    InvestorAccessOut,
    InvestorUpdateIn,
    InvestorUpdateOut,
    SecondaryDecideIn,
    SecondaryRequestIn,
    SPVCommitIn,
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
    require_write(ctx.role)
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


@router.post("/entities/{entity_id}/investor-updates", response_model=InvestorUpdateOut, status_code=201)
def publish_update(
    body: InvestorUpdateIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    upd = InvestorUpdate(
        entity_id=ctx.entity.id, title=body.title, body=body.body, created_by=user.id
    )
    db.add(upd)
    db.commit()
    db.refresh(upd)
    return upd


@router.get("/entities/{entity_id}/investor-updates", response_model=list[InvestorUpdateOut])
def list_updates(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return (
        db.query(InvestorUpdate)
        .filter_by(entity_id=ctx.entity.id)
        .order_by(InvestorUpdate.created_at.desc())
        .all()
    )


# --- investor side: scoped read-only portal (any authenticated user) ---
@router.get("/portal")
def my_portal(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return svc.portal_for_user(db, user)


# --- portal PDF: LPs download their own statements / Form 64C by email match ---
@router.get("/portal/documents/{document_id}/pdf")
def portal_document_pdf(
    document_id: str,
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..models.esop import ExerciseRequest, ExerciseRequestStatus, Grant
    from ..services.esop import exercised_quantity, vested_quantity

    grant = db.get(Grant, body.grant_id)
    sh = db.get(Stakeholder, grant.stakeholder_id) if grant else None
    if grant is None or sh is None or sh.email != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Grant not found")
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    from ..models.spv import CoInvestor
    from ..services import spv as spv_svc

    ci = db.get(CoInvestor, body.co_investor_id)
    if ci is None or ci.email != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Invitation not found")
    ci = spv_svc.commit_to_spv(db, ci, body.amount, user.id)
    return {"id": ci.id, "status": ci.status, "commitment": str(ci.commitment)}


# --- secondary sales: the investor asks, the company decides (ROFR) ---
@router.post("/portal/secondary-requests", status_code=201)
def request_sale(
    body: SecondaryRequestIn,
    user: User = Depends(get_current_user),
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

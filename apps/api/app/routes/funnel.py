"""Fundraising funnel (FR-E-8): a public opt-in link per round. The admin side
is entity-scoped as usual; the /public endpoints are unauthenticated by design
— the token is the only credential, they expose only what a prospective
investor is meant to see, and submissions are rate-limited per IP."""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import EntityCtx, entity_ctx, get_current_user, get_owned, require_write
from ..models.crm import PipelineStage, ProspectInvestor
from ..models.dataroom import DataRoom, DataRoomAccessGrant, EngagementLog
from ..models.entity import LegalEntity
from ..models.funnel import FundraisingLink
from ..models.identity import User
from ..models.round import Commitment, Round
from ..ratelimit import funnel_limiter
from ..schemas import FunnelInterestIn, FunnelLinkIn, FunnelLinkOut
from ..services.notification import notify

router = APIRouter(tags=["funnel"])


# --- admin side ---
@router.post(
    "/entities/{entity_id}/rounds/{round_id}/funnel-link",
    response_model=FunnelLinkOut,
    status_code=201,
)
def create_link(
    round_id: str,
    body: FunnelLinkIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    get_owned(db, Round, round_id, ctx.entity.id, "round")
    if body.data_room_id:
        get_owned(db, DataRoom, body.data_room_id, ctx.entity.id, "data room")
    link = db.query(FundraisingLink).filter_by(round_id=round_id).first()
    if link is None:
        link = FundraisingLink(
            entity_id=ctx.entity.id, round_id=round_id, created_by=user.id
        )
        db.add(link)
    link.data_room_id = body.data_room_id
    link.active = True
    db.commit()
    db.refresh(link)
    return link


@router.get("/entities/{entity_id}/rounds/{round_id}/funnel")
def funnel(
    round_id: str, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    get_owned(db, Round, round_id, ctx.entity.id, "round")
    link = db.query(FundraisingLink).filter_by(round_id=round_id).first()
    commitments_by_email = {
        c.investor_email: c
        for c in db.query(Commitment).filter_by(round_id=round_id)
        if c.investor_email
    }
    views: dict[str, int] = {}
    if link and link.data_room_id:
        for log in db.query(EngagementLog).filter_by(data_room_id=link.data_room_id):
            views[log.actor] = views.get(log.actor, 0) + 1
    prospects = []
    for p in db.query(ProspectInvestor).filter_by(entity_id=ctx.entity.id, round_id=round_id):
        c = commitments_by_email.get(p.email) if p.email else None
        prospects.append({
            "id": p.id,
            "name": p.name,
            "firm": p.firm,
            "email": p.email,
            "stage": p.stage.value,
            "check_size": str(p.check_size) if p.check_size is not None else None,
            "last_contact": p.last_contact,
            "data_room_views": views.get(p.email, 0) if p.email else 0,
            "commitment": (
                {"id": c.id, "amount": str(c.amount), "status": c.status.value}
                if c else None
            ),
        })
    return {
        "link": (
            {"token": link.token, "active": link.active, "data_room_id": link.data_room_id}
            if link else None
        ),
        "prospects": prospects,
    }


@router.post("/entities/{entity_id}/rounds/{round_id}/funnel-link/deactivate", response_model=FunnelLinkOut)
def deactivate_link(
    round_id: str, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    get_owned(db, Round, round_id, ctx.entity.id, "round")
    link = db.query(FundraisingLink).filter_by(round_id=round_id).first()
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No funnel link for this round")
    link.active = False
    db.commit()
    db.refresh(link)
    return link


# --- public side (token is the credential) ---
def _active_link(db: Session, token: str) -> FundraisingLink:
    link = db.query(FundraisingLink).filter_by(token=token).first()
    if link is None or not link.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This link is no longer available")
    return link


@router.get("/public/funnel/{token}")
def public_info(token: str, db: Session = Depends(get_db)):
    link = _active_link(db, token)
    entity = db.get(LegalEntity, link.entity_id)
    rnd = db.get(Round, link.round_id)
    return {
        "company": entity.name if entity else None,
        "round": rnd.name if rnd else None,
        "instrument": rnd.instrument.value if rnd else None,
        "target_amount": str(rnd.target_amount) if rnd else None,
        "has_data_room": link.data_room_id is not None,
    }


@router.post("/public/funnel/{token}/interest", status_code=201)
def register_interest(
    token: str, body: FunnelInterestIn, request: Request, db: Session = Depends(get_db)
):
    ip = request.client.host if request.client else "unknown"
    if funnel_limiter.blocked(ip):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many submissions; try again later")
    funnel_limiter.record_failure(ip)  # every attempt counts toward the window

    link = _active_link(db, token)
    prospect = (
        db.query(ProspectInvestor)
        .filter_by(entity_id=link.entity_id, round_id=link.round_id, email=body.email)
        .first()
    )
    if prospect is None:
        prospect = ProspectInvestor(
            entity_id=link.entity_id,
            round_id=link.round_id,
            email=body.email,
            name=body.name,
            stage=PipelineStage.CONTACTED,
        )
        db.add(prospect)
        entity = db.get(LegalEntity, link.entity_id)
        notify(
            db, link.created_by, "funnel_interest",
            f"New investor interest: {body.name}",
            f"{body.name} ({body.email}) opted in via the funnel link"
            f"{f' of {entity.name}' if entity else ''}.",
        )
    prospect.name = body.name
    prospect.firm = body.firm
    prospect.check_size = body.check_size
    prospect.notes = body.notes
    prospect.last_contact = today_ist()

    data_room_granted = False
    if link.data_room_id:
        grant = (
            db.query(DataRoomAccessGrant)
            .filter_by(data_room_id=link.data_room_id, email=body.email)
            .first()
        )
        if grant is None:
            db.add(DataRoomAccessGrant(data_room_id=link.data_room_id, email=body.email))
        data_room_granted = True
    db.commit()
    return {"status": "ok", "data_room_granted": data_room_granted}

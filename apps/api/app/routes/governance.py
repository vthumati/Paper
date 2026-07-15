import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    DirectorCtx,
    EntityCtx,
    MeetingCtx,
    ResolutionCtx,
    director_ctx,
    entity_ctx,
    get_current_user,
    meeting_ctx,
    require_write,
    resolution_ctx,
)
from ..models.governance import AgendaItem, DirectorOfficer, Meeting, Resolution, ResolutionType
from ..models.identity import User
from ..models.portal import InvestorAccess, InvestorConsent
from ..schemas import (
    AgendaItemIn,
    CharterAmendmentIn,
    DirectorIn,
    DirectorOut,
    DirectorResignIn,
    DocumentOut,
    MeetingIn,
    MeetingOut,
    MinutesIn,
    ResolutionIn,
    ResolutionOut,
    ResolutionStatusIn,
)
from ..services import document as docsvc
from ..services import governance as svc
from ..services.compliance import add_obligation

router = APIRouter(tags=["governance"])


# --- meetings ---
@router.post("/entities/{entity_id}/meetings", response_model=MeetingOut, status_code=201)
def create_meeting(
    body: MeetingIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    mtg = Meeting(entity_id=ctx.entity.id, **body.model_dump())
    db.add(mtg)
    db.commit()
    db.refresh(mtg)
    return mtg


@router.get("/entities/{entity_id}/meetings", response_model=list[MeetingOut])
def list_meetings(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(Meeting).filter_by(entity_id=ctx.entity.id).all()


@router.get("/meetings/{meeting_id}", response_model=MeetingOut)
def get_meeting(ctx: MeetingCtx = Depends(meeting_ctx)):
    return ctx.meeting


@router.post("/meetings/{meeting_id}/minutes", response_model=MeetingOut)
def record_minutes(
    body: MinutesIn, ctx: MeetingCtx = Depends(meeting_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ctx.meeting.minutes = body.minutes
    ctx.meeting.status = body.status
    db.commit()
    db.refresh(ctx.meeting)
    return ctx.meeting


@router.post("/meetings/{meeting_id}/agenda", response_model=MeetingOut, status_code=201)
def add_agenda_item(
    body: AgendaItemIn, ctx: MeetingCtx = Depends(meeting_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    db.add(
        AgendaItem(meeting_id=ctx.meeting.id, title=body.title, order_index=body.order_index)
    )
    db.commit()
    db.refresh(ctx.meeting)
    return ctx.meeting


@router.post("/meetings/{meeting_id}/notice", response_model=DocumentOut, status_code=201)
def generate_notice(
    ctx: MeetingCtx = Depends(meeting_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = svc.generate_notice(db, ctx.meeting, user.id, today_ist())
    return docsvc.document_view(db, doc)


# --- directors / KMP register ---
@router.post("/entities/{entity_id}/directors", response_model=DirectorOut, status_code=201)
def appoint_director(
    body: DirectorIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    d = DirectorOfficer(entity_id=ctx.entity.id, **body.model_dump())
    db.add(d)
    db.flush()
    # event-based filing: DIR-12 for the appointment, due within 30 days
    add_obligation(
        db,
        ctx.entity.id,
        form_code="DIR-12",
        title=f"Director appointment (DIR-12) — {d.name}",
        category="ROC",
        due_date=d.appointed_on + datetime.timedelta(days=30),
        period_label=f"DIR-{d.id[:8]}-appt",
    )
    db.commit()
    db.refresh(d)
    return d


@router.get("/entities/{entity_id}/directors", response_model=list[DirectorOut])
def list_directors(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(DirectorOfficer).filter_by(entity_id=ctx.entity.id).all()


@router.post("/directors/{director_id}/resign", response_model=DirectorOut)
def resign_director(
    body: DirectorResignIn, ctx: DirectorCtx = Depends(director_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ctx.director.resigned_on = body.resigned_on
    ctx.director.status = "resigned"
    add_obligation(
        db,
        ctx.director.entity_id,
        form_code="DIR-12",
        title=f"Director resignation (DIR-12) — {ctx.director.name}",
        category="ROC",
        due_date=body.resigned_on + datetime.timedelta(days=30),
        period_label=f"DIR-{ctx.director.id[:8]}-resign",
    )
    db.commit()
    db.refresh(ctx.director)
    return ctx.director


@router.post("/directors/{director_id}/indemnification", response_model=DocumentOut, status_code=201)
def generate_indemnification(
    ctx: DirectorCtx = Depends(director_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = svc.generate_indemnification(db, ctx.director, user.id, today_ist())
    return docsvc.document_view(db, doc)


# --- resolutions ---
@router.post("/entities/{entity_id}/resolutions", response_model=ResolutionOut, status_code=201)
def create_resolution(
    body: ResolutionIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    res = Resolution(entity_id=ctx.entity.id, **body.model_dump())
    db.add(res)
    db.commit()
    db.refresh(res)
    return res


@router.get("/entities/{entity_id}/resolutions", response_model=list[ResolutionOut])
def list_resolutions(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(Resolution).filter_by(entity_id=ctx.entity.id).all()


@router.post("/resolutions/{resolution_id}/status", response_model=ResolutionOut)
def set_status(
    body: ResolutionStatusIn, ctx: ResolutionCtx = Depends(resolution_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    return svc.set_resolution_status(db, ctx.resolution, body.status, today_ist())


@router.post("/resolutions/{resolution_id}/document", response_model=DocumentOut, status_code=201)
def generate_resolution_document(
    ctx: ResolutionCtx = Depends(resolution_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = svc.generate_document(db, ctx.resolution, user.id, today_ist())
    return docsvc.document_view(db, doc)


# --- charter (MoA/AoA) amendment: special resolution + document in one step ---
@router.post("/entities/{entity_id}/charter-amendments", status_code=201)
def charter_amendment(
    body: CharterAmendmentIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    kind = body.kind.upper()
    res = Resolution(
        entity_id=ctx.entity.id,
        type=ResolutionType.SPECIAL,
        title=f"Charter amendment ({kind}) — {body.description[:180]}",
        text=body.description,
    )
    db.add(res)
    db.flush()
    doc = docsvc.create_document(
        db, entity_id=ctx.entity.id, template_key="charter_amendment",
        data={"company": ctx.entity.name, "kind": kind, "date": today_ist().isoformat(),
              "description": body.description, "resolution_title": res.title},
        user_id=user.id, title=f"Charter amendment ({kind})",
        subject_type="resolution", subject_id=res.id,
    )
    res.document_id = doc.id
    db.commit()
    # passing the special resolution later auto-adds the MGT-14 obligation
    return {"resolution_id": res.id, "document_id": doc.id, "status": res.status.value}


# --- investor consents on a resolution (SHA reserved matters) ---
@router.post("/resolutions/{resolution_id}/consents")
def request_consents(
    ctx: ResolutionCtx = Depends(resolution_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    res = ctx.resolution
    existing = {
        c.email for c in db.query(InvestorConsent).filter_by(resolution_id=res.id)
    }
    created = 0
    for a in db.query(InvestorAccess).filter_by(entity_id=res.entity_id):
        if a.email in existing:
            continue
        db.add(InvestorConsent(entity_id=res.entity_id, resolution_id=res.id, email=a.email))
        existing.add(a.email)
        created += 1
    db.commit()
    if created == 0 and not existing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No investors have portal access — invite them under Investors first",
        )
    return {"requested": created, "total": len(existing)}


@router.get("/resolutions/{resolution_id}/consents")
def list_consents(ctx: ResolutionCtx = Depends(resolution_ctx), db: Session = Depends(get_db)):
    rows = db.query(InvestorConsent).filter_by(resolution_id=ctx.resolution.id).all()
    tally = {"approved": 0, "rejected": 0, "pending": 0}
    for c in rows:
        tally[c.status.value] += 1
    return {
        "tally": tally,
        "consents": [
            {"id": c.id, "email": c.email, "status": c.status.value, "decided_at": c.decided_at}
            for c in rows
        ],
    }

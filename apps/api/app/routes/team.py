
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    TeamMemberCtx,
    entity_ctx,
    get_current_user,
    require_write,
    team_member_ctx,
)
from ..models.identity import User
from ..models.team import TeamMember
from ..schemas import (
    DocumentOut,
    TeamDocIn,
    TeamMemberIn,
    TeamMemberOut,
    TeamMemberStatusIn,
    TeamOffboardIn,
)
from ..services import document as docsvc
from ..services import team as svc

router = APIRouter(tags=["team"])


@router.post("/entities/{entity_id}/team", response_model=TeamMemberOut, status_code=201)
def add_member(
    body: TeamMemberIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    member = TeamMember(entity_id=ctx.entity.id, **body.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/entities/{entity_id}/team", response_model=list[TeamMemberOut])
def list_team(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(TeamMember).filter_by(entity_id=ctx.entity.id).all()


@router.post("/team/{member_id}/status", response_model=TeamMemberOut)
def update_status(
    body: TeamMemberStatusIn, ctx: TeamMemberCtx = Depends(team_member_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ctx.member.status = body.status
    if body.left_on is not None:
        ctx.member.left_on = body.left_on
    db.commit()
    db.refresh(ctx.member)
    return ctx.member


@router.post("/team/{member_id}/offboard")
def offboard(
    body: TeamOffboardIn,
    ctx: TeamMemberCtx = Depends(team_member_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.offboard(db, ctx.member, body.left_on or today_ist())


@router.post("/team/{member_id}/documents", response_model=DocumentOut, status_code=201)
def generate_document(
    body: TeamDocIn,
    ctx: TeamMemberCtx = Depends(team_member_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = svc.generate_document(db, ctx.member, body.template_key, user.id, today_ist())
    return docsvc.document_view(db, doc)


@router.post("/team/{member_id}/onboard")
def onboard(
    ctx: TeamMemberCtx = Depends(team_member_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.onboard(db, ctx.member, user.id, today_ist())

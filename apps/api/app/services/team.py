"""Team & HR-Legal service (FR-R). Generates HR documents and runs an
onboarding bundle that links a cap-table stakeholder (so the person can later
receive ESOP grants)."""
import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..documents.templates import REGISTRY
from ..models.captable import Stakeholder, StakeholderType
from ..models.entity import LegalEntity
from ..models.team import TeamMember
from . import document as docsvc

HR_TEMPLATES = {"offer_letter", "ip_assignment", "nda"}


def _doc_data(entity: LegalEntity, member: TeamMember, as_of: datetime.date) -> dict:
    return {
        "company": entity.name if entity else "",
        "name": member.name,
        "title": member.title or "",
        "date": as_of.isoformat(),
    }


def generate_document(db: Session, member: TeamMember, template_key: str, user_id: str, as_of: datetime.date):
    if template_key not in HR_TEMPLATES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Not an HR template: {template_key}")
    entity = db.get(LegalEntity, member.entity_id)
    return docsvc.create_document(
        db,
        entity_id=member.entity_id,
        template_key=template_key,
        data=_doc_data(entity, member, as_of),
        user_id=user_id,
        title=f"{REGISTRY[template_key].name} — {member.name}",
        subject_type="team_member",
        subject_id=member.id,
    )


def offboard(db: Session, member: TeamMember, left_on: datetime.date) -> dict:
    """Exit a team member and lapse their unvested options (FR-R-4): each
    grant is cut down to what had vested by the leaving date, so the lapsed
    options return to the scheme pool automatically (pool usage is the sum of
    grant quantities)."""
    from ..models.esop import ForfeitureEvent, Grant
    from .esop import vested_quantity

    member.status = "exited"
    member.left_on = left_on
    lapsed = 0
    affected = 0
    if member.stakeholder_id:
        for grant in db.query(Grant).filter_by(
            entity_id=member.entity_id, stakeholder_id=member.stakeholder_id
        ):
            vested = vested_quantity(grant, left_on)
            if grant.quantity > vested:
                this_lapse = grant.quantity - vested
                lapsed += this_lapse
                grant.quantity = vested  # vesting freezes at the exit date
                affected += 1
                # auditable true-up: record what lapsed and what vested-vested
                db.add(
                    ForfeitureEvent(
                        entity_id=member.entity_id,
                        grant_id=grant.id,
                        stakeholder_id=member.stakeholder_id,
                        lapsed_quantity=this_lapse,
                        vested_retained=vested,
                        reason="offboarding",
                        date=left_on,
                    )
                )
    db.commit()
    return {"member_id": member.id, "lapsed_options": lapsed, "grants_affected": affected}


def onboard(db: Session, member: TeamMember, user_id: str, as_of: datetime.date) -> dict:
    # ensure a cap-table stakeholder exists for ESOP eligibility
    if not member.stakeholder_id:
        sh = Stakeholder(
            entity_id=member.entity_id,
            name=member.name,
            type=StakeholderType.EMPLOYEE,
            email=member.email,
        )
        db.add(sh)
        db.flush()
        member.stakeholder_id = sh.id
        db.commit()

    docs = [
        generate_document(db, member, tk, user_id, as_of)
        for tk in ("offer_letter", "ip_assignment", "nda")
    ]
    return {"stakeholder_id": member.stakeholder_id, "documents": [d.id for d in docs]}

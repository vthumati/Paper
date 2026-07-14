"""Governance service (FR-G): pass/fail resolutions and generate a linked
board-resolution document."""
import datetime

from sqlalchemy.orm import Session

import datetime as _dt

from ..models.entity import LegalEntity
from ..models.governance import (
    AgendaItem,
    DirectorOfficer,
    Meeting,
    Resolution,
    ResolutionStatus,
    ResolutionType,
)
from . import document as docsvc
from .compliance import add_obligation


def set_resolution_status(
    db: Session, res: Resolution, new_status: ResolutionStatus, as_of: datetime.date
) -> Resolution:
    res.status = new_status
    res.passed_date = as_of if new_status == ResolutionStatus.PASSED else None
    # event-based filing: special resolutions must be filed in MGT-14 within 30 days
    if new_status == ResolutionStatus.PASSED and res.type in (
        ResolutionType.SPECIAL,
        ResolutionType.CIRCULAR,
    ):
        add_obligation(
            db,
            res.entity_id,
            form_code="MGT-14",
            title=f"File resolution (MGT-14) — {res.title}",
            category="ROC",
            due_date=as_of + _dt.timedelta(days=30),
            period_label=f"RES-{res.id[:8]}",
        )
    db.commit()
    db.refresh(res)
    return res


def generate_document(db: Session, res: Resolution, user_id: str, as_of: datetime.date):
    entity = db.get(LegalEntity, res.entity_id)
    doc = docsvc.create_document(
        db,
        entity_id=res.entity_id,
        template_key="board_resolution",
        data={
            "company": entity.name if entity else "",
            "date": as_of.isoformat(),
            "resolution_text": res.text,
            "signatory": "Director",
        },
        user_id=user_id,
        title=res.title,
        subject_type="resolution",
        subject_id=res.id,
    )
    res.document_id = doc.id
    db.commit()
    db.refresh(res)
    return doc


def generate_notice(db: Session, meeting: Meeting, user_id: str, as_of: datetime.date):
    entity = db.get(LegalEntity, meeting.entity_id)
    items = (
        db.query(AgendaItem)
        .filter_by(meeting_id=meeting.id)
        .order_by(AgendaItem.order_index)
        .all()
    )
    agenda = "\n".join(f"{i + 1}. {it.title}" for i, it in enumerate(items)) or "(no items)"
    doc = docsvc.create_document(
        db,
        entity_id=meeting.entity_id,
        template_key="meeting_notice",
        data={
            "company": entity.name if entity else "",
            "meeting_type": meeting.type.value.upper(),
            "date": meeting.date.isoformat(),
            "venue": meeting.location or "the registered office",
            "agenda": agenda,
            "quorum": str(meeting.quorum) if meeting.quorum else "as per Articles",
        },
        user_id=user_id,
        title=f"Notice — {meeting.title}",
        subject_type="meeting",
        subject_id=meeting.id,
    )
    meeting.notice_document_id = doc.id
    db.commit()
    db.refresh(meeting)
    return doc


def generate_indemnification(db: Session, director: DirectorOfficer, user_id: str, as_of: datetime.date):
    entity = db.get(LegalEntity, director.entity_id)
    return docsvc.create_document(
        db,
        entity_id=director.entity_id,
        template_key="indemnification",
        data={
            "company": entity.name if entity else "",
            "name": director.name,
            "designation": director.designation.value.replace("_", " "),
            "date": as_of.isoformat(),
        },
        user_id=user_id,
        title=f"D&O Indemnification — {director.name}",
        subject_type="director",
        subject_id=director.id,
    )

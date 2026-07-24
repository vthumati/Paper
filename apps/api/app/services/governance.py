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
    MeetingAttendee,
    Resolution,
    ResolutionStatus,
    ResolutionType,
    ResolutionVote,
    VoteChoice,
)
from . import document as docsvc
from .compliance import add_obligation


def add_attendee(db: Session, meeting: Meeting, name: str, role: str, present: bool) -> MeetingAttendee:
    att = MeetingAttendee(meeting_id=meeting.id, name=name, role=role or "director", present=present)
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


def record_vote(db: Session, res: Resolution, voter: str, vote: VoteChoice, shares: int) -> ResolutionVote:
    v = ResolutionVote(resolution_id=res.id, voter=voter, vote=vote, shares=max(0, shares))
    db.add(v)
    db.commit()
    db.refresh(v)
    return v


def vote_tally(db: Session, res: Resolution) -> dict:
    """For/against/abstain head-count and share-weighted tally for a resolution."""
    heads = {"for": 0, "against": 0, "abstain": 0}
    shares = {"for": 0, "against": 0, "abstain": 0}
    for v in db.query(ResolutionVote).filter_by(resolution_id=res.id):
        heads[v.vote.value] += 1
        shares[v.vote.value] += v.shares
    return {
        "for": heads["for"], "against": heads["against"], "abstain": heads["abstain"],
        "for_shares": shares["for"], "against_shares": shares["against"],
        "abstain_shares": shares["abstain"],
        "total": heads["for"] + heads["against"] + heads["abstain"],
    }


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


def _decision_block(db: Session, res: Resolution) -> str:
    """The 'Present: …' + 'Result: …' block folded into the resolution document,
    drawn from the meeting's attendees and the recorded votes (empty if none)."""
    lines = []
    if res.meeting_id:
        present = [
            a.name
            for a in db.query(MeetingAttendee).filter_by(meeting_id=res.meeting_id, present=True)
        ]
        if present:
            lines.append(f"Present: {', '.join(present)} ({len(present)} present)")
    t = vote_tally(db, res)
    if t["total"]:
        line = f"Result: For {t['for']}, Against {t['against']}, Abstain {t['abstain']}"
        if t["for_shares"] or t["against_shares"]:
            line += (
                f" (share-weighted — for {t['for_shares']:,}, "
                f"against {t['against_shares']:,}, abstain {t['abstain_shares']:,})"
            )
        lines.append(line)
    return ("\n".join(lines) + "\n\n") if lines else ""


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
            "decision": _decision_block(db, res),
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

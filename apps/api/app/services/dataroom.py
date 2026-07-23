"""Data Room service (FR-I): rooms, items (links to documents), access grants,
and engagement logging."""
from sqlalchemy.orm import Session

from ..models.dataroom import DataRoom, EngagementLog
from ..models.document import Document


def data_room_view(db: Session, room: DataRoom) -> dict:
    docs = {
        d.id: d
        for d in db.query(Document).filter(
            Document.id.in_([i.document_id for i in room.items])
        )
    }
    return {
        "id": room.id,
        "entity_id": room.entity_id,
        "name": room.name,
        "scope": room.scope,
        "items": [
            {
                "id": i.id,
                "document_id": i.document_id,
                "document_title": docs[i.document_id].title if i.document_id in docs else None,
                "folder": i.folder,
                "order_index": i.order_index,
            }
            for i in room.items
        ],
        "grants": [
            {"id": g.id, "email": g.email, "permissions": g.permissions, "expiry": g.expiry}
            for g in room.grants
        ],
    }


def log_engagement(db: Session, room_id: str, document_id: str | None, actor: str, action: str):
    db.add(
        EngagementLog(data_room_id=room_id, document_id=document_id, actor=actor, action=action)
    )
    db.commit()


def engagement_summary(db: Session, room_id: str) -> list[dict]:
    """Per (document, viewer): how many times they opened it, and when they
    first and last did — the founder's "who accessed the deck, when" signal.
    Ordered most-recently-active first."""
    logs = (
        db.query(EngagementLog)
        .filter_by(data_room_id=room_id)
        .order_by(EngagementLog.created_at)
        .all()
    )
    doc_ids = {lg.document_id for lg in logs if lg.document_id}
    titles = {
        d.id: d.title
        for d in (db.query(Document).filter(Document.id.in_(doc_ids)).all() if doc_ids else [])
    }
    agg: dict[tuple[str | None, str], dict] = {}
    for lg in logs:  # ascending, so last write wins for last_viewed
        key = (lg.document_id, lg.actor)
        row = agg.get(key)
        if row is None:
            agg[key] = {
                "document_id": lg.document_id,
                "document_name": titles.get(lg.document_id),
                "actor": lg.actor,
                "views": 1,
                "first_viewed": lg.created_at,
                "last_viewed": lg.created_at,
            }
        else:
            row["views"] += 1
            row["last_viewed"] = lg.created_at
    return sorted(agg.values(), key=lambda r: r["last_viewed"], reverse=True)

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
    logs = db.query(EngagementLog).filter_by(data_room_id=room_id).all()
    counts: dict[tuple[str | None, str], int] = {}
    for lg in logs:
        key = (lg.document_id, lg.actor)
        counts[key] = counts.get(key, 0) + 1
    return [
        {"document_id": doc_id, "actor": actor, "views": n}
        for (doc_id, actor), n in counts.items()
    ]

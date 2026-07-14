"""Services marketplace helpers (FR-O): present engagements with their
provider details joined in."""
from sqlalchemy.orm import Session

from ..models.marketplace import ServiceEngagement, ServiceProvider


def engagement_view(db: Session, eng: ServiceEngagement) -> dict:
    p = db.get(ServiceProvider, eng.provider_id)
    return {
        "id": eng.id,
        "entity_id": eng.entity_id,
        "provider_id": eng.provider_id,
        "provider_name": p.name if p else None,
        "provider_category": p.category.value if p else None,
        "scope": eng.scope,
        "status": eng.status,
        "deliverable_doc_id": eng.deliverable_doc_id,
    }

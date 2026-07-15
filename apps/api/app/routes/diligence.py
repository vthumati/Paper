
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EntityCtx, entity_ctx, get_current_user, require_write
from ..models.identity import User
from ..schemas import DocumentOut
from ..services import diligence as svc
from ..services import document as docsvc

router = APIRouter(tags=["diligence"])


@router.get("/entities/{entity_id}/diligence")
def diligence(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return svc.run_diligence(db, ctx.entity.id)


@router.post("/entities/{entity_id}/diligence/report", response_model=DocumentOut, status_code=201)
def diligence_report(
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = svc.generate_report(db, ctx.entity.id, user.id)
    return docsvc.document_view(db, doc)

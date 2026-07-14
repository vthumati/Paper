from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EntityCtx, PageCtx, entity_ctx, page, require_write
from ..models.document import Document
from ..models.tax import TaxRecord
from ..schemas import FileOut, TaxRecordIn, TaxRecordOut
from ..services.dashboard import entity_dashboard

router = APIRouter(tags=["workspace"])


@router.get("/entities/{entity_id}/dashboard")
def dashboard(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return entity_dashboard(db, ctx.entity)


@router.get("/entities/{entity_id}/files", response_model=list[FileOut])
def file_cabinet(
    q: str | None = None,
    p: PageCtx = Depends(page),
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    query = db.query(Document).filter_by(entity_id=ctx.entity.id)
    if q:
        query = query.filter(Document.title.ilike(f"%{q}%"))
    docs = (
        query.order_by(Document.created_at.desc()).offset(p.offset).limit(p.limit).all()
    )
    return [
        FileOut(
            id=d.id,
            title=d.title,
            type=d.type,
            status=d.status.value,
            current_version=d.current_version,
            subject_type=d.subject_type,
            created_at=d.created_at,
        )
        for d in docs
    ]


@router.post("/entities/{entity_id}/tax-records", response_model=TaxRecordOut, status_code=201)
def add_tax_record(
    body: TaxRecordIn,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    rec = TaxRecord(entity_id=ctx.entity.id, **body.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/entities/{entity_id}/tax-records", response_model=list[TaxRecordOut])
def list_tax_records(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(TaxRecord).filter_by(entity_id=ctx.entity.id).all()

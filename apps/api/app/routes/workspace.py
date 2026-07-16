from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import EntityCtx, PageCtx, entity_ctx, get_current_user, page, require_write
from ..models.document import Document
from ..models.identity import User
from ..models.tax import TaxRecord
from ..schemas import DocumentOut, FileOut, InvestorReportIn, TaxRecordIn, TaxRecordOut
from ..services import document as docsvc
from ..services import reporting as repsvc
from ..services.dashboard import entity_dashboard
from ..services.tasks import entity_tasks

router = APIRouter(tags=["workspace"])


@router.get("/entities/{entity_id}/dashboard")
def dashboard(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return entity_dashboard(db, ctx.entity)


@router.get("/entities/{entity_id}/tasks")
def tasks(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    """Everything actionable for this entity, ranked (FR-T-4)."""
    return entity_tasks(db, ctx.entity.id)


@router.get("/entities/{entity_id}/investor-report/preview")
def investor_report_preview(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    """Assembled metrics for a periodic investor report (FR-K-4)."""
    return repsvc.report_metrics(db, ctx.entity)


@router.post("/entities/{entity_id}/investor-reports", response_model=DocumentOut, status_code=201)
def create_investor_report(
    body: InvestorReportIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    data = repsvc.build_report_data(db, ctx.entity, body.period_label, body.highlights)
    doc = docsvc.create_document(
        db,
        entity_id=ctx.entity.id,
        template_key="investor_report",
        data=data,
        user_id=user.id,
        title=f"Investor report — {body.period_label}",
        subject_type="investor_report",
        subject_id=ctx.entity.id,
    )
    return docsvc.document_view(db, doc)


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

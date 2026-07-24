from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ...clock import today_ist
from ...db import get_db
from ...deps import FundCtx, fund_ctx, get_current_user, require_write
from ...models.entity import LegalEntity
from ...models.identity import User
from ...schemas import DDQEntryIn, DDQEntryUpdateIn, DocumentOut
from ...services import document as docsvc
from ...services import fund as svc

router = APIRouter(tags=["fund"])


# --- DDQ answer bank: due-diligence questionnaire responses ---
@router.get("/funds/{fund_id}/ddq")
def list_ddq(ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)):
    return {"entries": svc.list_ddq(db, ctx.fund), "presets": svc.DDQ_PRESETS}


@router.post("/funds/{fund_id}/ddq", status_code=201)
def create_ddq_entry(
    body: DDQEntryIn,
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.create_ddq_entry(db, ctx.fund, body.model_dump(), user.id)


@router.put("/funds/{fund_id}/ddq/{entry_id}")
def update_ddq_entry(
    entry_id: str,
    body: DDQEntryUpdateIn,
    ctx: FundCtx = Depends(fund_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.update_ddq_entry(db, ctx.fund, entry_id, body.model_dump(exclude_unset=True))


@router.delete("/funds/{fund_id}/ddq/{entry_id}", status_code=204)
def delete_ddq_entry(
    entry_id: str, ctx: FundCtx = Depends(fund_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    svc.delete_ddq_entry(db, ctx.fund, entry_id)


@router.post("/funds/{fund_id}/ddq/report", response_model=DocumentOut, status_code=201)
def ddq_report(
    ctx: FundCtx = Depends(fund_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    entity = db.get(LegalEntity, ctx.fund.entity_id)
    doc = docsvc.create_document(
        db,
        entity_id=ctx.fund.entity_id,
        template_key="ddq",
        data={
            "fund": entity.name if entity else "",
            "category": ctx.fund.sebi_category.value,
            "date": today_ist().isoformat(),
            "sections": svc.ddq_sections(db, ctx.fund),
        },
        user_id=user.id,
        title="DDQ Responses",
        subject_type="ddq",
        subject_id=ctx.fund.id,
    )
    return docsvc.document_view(db, doc)

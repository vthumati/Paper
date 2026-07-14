import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    ContractCtx,
    EntityCtx,
    contract_ctx,
    entity_ctx,
    get_current_user,
    require_write,
)
from ..models.clm import Contract, Counterparty
from ..models.entity import LegalEntity
from ..models.identity import User
from ..schemas import (
    ContractDocIn,
    ContractIn,
    ContractOut,
    ContractStatusIn,
    CounterpartyIn,
    CounterpartyOut,
    DocumentOut,
)
from ..services import clm as svc
from ..services import document as docsvc

router = APIRouter(tags=["clm"])

_CONTRACT_TEMPLATES = {"msa", "sow", "nda"}


# --- counterparties ---
@router.post("/entities/{entity_id}/counterparties", response_model=CounterpartyOut, status_code=201)
def add_counterparty(
    body: CounterpartyIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    cp = Counterparty(entity_id=ctx.entity.id, **body.model_dump())
    db.add(cp)
    db.commit()
    db.refresh(cp)
    return cp


@router.get("/entities/{entity_id}/counterparties", response_model=list[CounterpartyOut])
def list_counterparties(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(Counterparty).filter_by(entity_id=ctx.entity.id).all()


# --- contracts ---
@router.post("/entities/{entity_id}/contracts", response_model=ContractOut, status_code=201)
def add_contract(
    body: ContractIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    cp = db.get(Counterparty, body.counterparty_id)
    if cp is None or cp.entity_id != ctx.entity.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown counterparty for this entity")
    c = Contract(entity_id=ctx.entity.id, **body.model_dump())
    db.add(c)
    db.commit()
    db.refresh(c)
    return svc.contract_view(db, c, today_ist())


@router.get("/entities/{entity_id}/contracts", response_model=list[ContractOut])
def list_contracts(
    as_of: datetime.date | None = None,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    ref = as_of or today_ist()
    contracts = db.query(Contract).filter_by(entity_id=ctx.entity.id).all()
    return [svc.contract_view(db, c, ref) for c in contracts]


@router.get("/entities/{entity_id}/contracts/renewals", response_model=list[ContractOut])
def renewals_due(
    within_days: int = 30,
    as_of: datetime.date | None = None,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    return svc.renewals_due(db, ctx.entity.id, within_days, as_of or today_ist())


@router.post("/contracts/{contract_id}/status", response_model=ContractOut)
def update_status(
    body: ContractStatusIn, ctx: ContractCtx = Depends(contract_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    ctx.contract.status = body.status
    db.commit()
    db.refresh(ctx.contract)
    return svc.contract_view(db, ctx.contract, today_ist())


@router.post("/contracts/{contract_id}/document", response_model=DocumentOut, status_code=201)
def generate_document(
    body: ContractDocIn,
    ctx: ContractCtx = Depends(contract_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    if body.template_key not in _CONTRACT_TEMPLATES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Not a contract template")
    c = ctx.contract
    entity = db.get(LegalEntity, c.entity_id)
    cp = db.get(Counterparty, c.counterparty_id)
    doc = docsvc.create_document(
        db,
        entity_id=c.entity_id,
        template_key=body.template_key,
        data={
            "company": entity.name if entity else "",
            "counterparty": cp.name if cp else "",
            "title": c.title,
            "value": str(c.value) if c.value is not None else "",
            "date": today_ist().isoformat(),
        },
        user_id=user.id,
        title=f"{c.title} — {cp.name if cp else ''}",
        subject_type="contract",
        subject_id=c.id,
    )
    c.document_id = doc.id
    db.commit()
    return docsvc.document_view(db, doc)

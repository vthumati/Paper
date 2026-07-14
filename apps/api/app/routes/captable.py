from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import EntityCtx, entity_ctx, get_owned, require_write
from ..models.captable import (
    BuybackTransaction,
    ConversionEvent,
    CorporateAction,
    IssuanceTransaction,
    SecurityClass,
    Stakeholder,
    TransferTransaction,
)
from ..schemas import (
    BuybackIn,
    CapTableImportIn,
    ConversionIn,
    ConversionOut,
    CorporateActionIn,
    CorporateActionOut,
    IssuanceIn,
    IssuanceOut,
    SecurityClassIn,
    SecurityClassOut,
    StakeholderIn,
    StakeholderOut,
    TransferIn,
    TransferOut,
)
from ..services import captable as svc
from ..services.captable import compute_cap_table
from ..services.diluted import anti_dilution_preview, fully_diluted
from ..services.importer import TEMPLATE, apply_import, parse_and_validate

router = APIRouter(prefix="/entities/{entity_id}", tags=["cap-table"])


# --- security classes ---
@router.post("/security-classes", response_model=SecurityClassOut, status_code=201)
def create_security_class(
    body: SecurityClassIn,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    sc = SecurityClass(entity_id=ctx.entity.id, **body.model_dump())
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


@router.get("/security-classes", response_model=list[SecurityClassOut])
def list_security_classes(
    ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    return db.query(SecurityClass).filter_by(entity_id=ctx.entity.id).all()


@router.get("/security-classes/{class_id}/anti-dilution")
def anti_dilution(
    class_id: str,
    new_price: float,
    new_shares: int,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    sc = db.get(SecurityClass, class_id)
    if not sc or sc.entity_id != ctx.entity.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Security class not found")
    return anti_dilution_preview(db, sc, Decimal(str(new_price)), new_shares)


# --- stakeholders ---
@router.post("/stakeholders", response_model=StakeholderOut, status_code=201)
def create_stakeholder(
    body: StakeholderIn,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    sh = Stakeholder(entity_id=ctx.entity.id, **body.model_dump())
    db.add(sh)
    db.commit()
    db.refresh(sh)
    return sh


@router.get("/stakeholders", response_model=list[StakeholderOut])
def list_stakeholders(
    ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    return db.query(Stakeholder).filter_by(entity_id=ctx.entity.id).all()


# --- issuances (append-only ledger) ---
@router.post("/issuances", response_model=IssuanceOut, status_code=201)
def create_issuance(
    body: IssuanceIn,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    eid = ctx.entity.id
    get_owned(db, SecurityClass, body.security_class_id, eid, "security class")
    get_owned(db, Stakeholder, body.stakeholder_id, eid, "stakeholder")
    if body.quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Quantity must be positive")
    txn = IssuanceTransaction(entity_id=eid, **body.model_dump())
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


@router.get("/cap-table")
def get_cap_table(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return compute_cap_table(db, ctx.entity.id)


@router.post("/cap-table/import")
def import_cap_table(
    body: CapTableImportIn,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    """Validate a cap-table CSV; with apply=true, create everything atomically."""
    require_write(ctx.role)
    report = parse_and_validate(db, ctx.entity.id, body.csv)
    if not body.apply:
        return report
    if not report["valid"]:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            {"message": "CSV has errors — nothing was imported", "errors": report["errors"]},
        )
    result = apply_import(db, ctx.entity.id, report["rows"])
    return {**report, "applied": True, **result}


@router.get("/cap-table/import-template")
def import_template(ctx: EntityCtx = Depends(entity_ctx)):
    return Response(
        content=TEMPLATE,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="cap-table-import.csv"'},
    )


@router.get("/cap-table/fully-diluted")
def get_fully_diluted(
    assumed_price: float | None = None,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    price = Decimal(str(assumed_price)) if assumed_price else None
    return fully_diluted(db, ctx.entity.id, price)


# --- transfers (SH-4) ---
@router.post("/transfers", response_model=TransferOut, status_code=201)
def create_transfer(
    body: TransferIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    eid = ctx.entity.id
    get_owned(db, SecurityClass, body.security_class_id, eid, "security class")
    for sh_id in (body.from_stakeholder_id, body.to_stakeholder_id):
        get_owned(db, Stakeholder, sh_id, eid, "stakeholder")
    if body.quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Quantity must be positive")
    held = svc.holding_quantity(db, eid, body.from_stakeholder_id, body.security_class_id)
    if body.quantity > held:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Transferor only holds {held}")
    consideration = body.quantity * body.price_per_unit
    txn = TransferTransaction(
        entity_id=eid,
        security_class_id=body.security_class_id,
        from_stakeholder_id=body.from_stakeholder_id,
        to_stakeholder_id=body.to_stakeholder_id,
        quantity=body.quantity,
        price_per_unit=body.price_per_unit,
        transfer_date=body.transfer_date or today_ist(),
        stamp_duty=svc.stamp_duty_on_transfer(consideration),
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)
    return txn


# --- conversions (e.g. CCPS/SAFE -> equity) ---
@router.post("/conversions", response_model=ConversionOut, status_code=201)
def create_conversion(
    body: ConversionIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    eid = ctx.entity.id
    for cls_id in (body.from_class_id, body.to_class_id):
        get_owned(db, SecurityClass, cls_id, eid, "security class")
    if body.from_quantity <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Quantity must be positive")
    held = svc.holding_quantity(db, eid, body.stakeholder_id, body.from_class_id)
    if body.from_quantity > held:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Holder only holds {held} of the source class")
    to_quantity = int(body.from_quantity * body.ratio)
    ev = ConversionEvent(
        entity_id=eid,
        stakeholder_id=body.stakeholder_id,
        from_class_id=body.from_class_id,
        to_class_id=body.to_class_id,
        from_quantity=body.from_quantity,
        to_quantity=to_quantity,
        date=today_ist(),
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    return ev


# --- buybacks ---
@router.post("/buybacks", status_code=201)
def create_buyback(
    body: BuybackIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    eid = ctx.entity.id
    held = svc.holding_quantity(db, eid, body.stakeholder_id, body.security_class_id)
    if body.quantity <= 0 or body.quantity > held:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Holder only holds {held}")
    bb = BuybackTransaction(
        entity_id=eid,
        security_class_id=body.security_class_id,
        stakeholder_id=body.stakeholder_id,
        quantity=body.quantity,
        price_per_unit=body.price_per_unit,
        date=today_ist(),
    )
    db.add(bb)
    db.commit()
    db.refresh(bb)
    return {"id": bb.id, "quantity": bb.quantity}


# --- corporate actions (split / bonus) ---
@router.post("/corporate-actions", response_model=CorporateActionOut, status_code=201)
def create_corporate_action(
    body: CorporateActionIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    get_owned(db, SecurityClass, body.security_class_id, ctx.entity.id, "security class")
    if body.numerator <= 0 or body.denominator <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "numerator/denominator must be positive")
    ca = CorporateAction(
        entity_id=ctx.entity.id,
        security_class_id=body.security_class_id,
        type=body.type,
        numerator=body.numerator,
        denominator=body.denominator,
        date=today_ist(),
    )
    db.add(ca)
    db.commit()
    db.refresh(ca)
    return ca


# --- liquidation waterfall ---
@router.get("/waterfall")
def waterfall(
    exit_amount: float,
    ctx: EntityCtx = Depends(entity_ctx),
    db: Session = Depends(get_db),
):
    return svc.liquidation_waterfall(db, ctx.entity.id, Decimal(str(exit_amount)))

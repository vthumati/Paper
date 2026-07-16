import csv
import io
from decimal import Decimal

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..db import get_db
from ..deps import (
    EntityCtx,
    InstrumentCtx,
    entity_ctx,
    get_current_user,
    instrument_ctx,
    require_write,
)
from ..models.compliance import ComplianceObligation
from ..models.identity import User
from ..models.instruments import ConvertibleInstrument, DematRecord
from ..schemas import (
    DematIn,
    DematOut,
    DocumentOut,
    InstrumentConvertIn,
    InstrumentIn,
    InstrumentOut,
    ResolutionOut,
)
from ..services import document as docsvc
from ..services import instruments as svc
from ..services.captable import compute_cap_table
from ..services.compliance import obligation_view
from ..services.placement import check_offeree_limit

router = APIRouter(tags=["instruments"])


# --- convertible instruments (SAFE / note) ---
@router.post("/entities/{entity_id}/instruments", response_model=InstrumentOut, status_code=201)
def create_instrument(
    body: InstrumentIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    check_offeree_limit(db, ctx.entity.id, body.investor_name, body.issue_date)
    inst = ConvertibleInstrument(entity_id=ctx.entity.id, **body.model_dump())
    db.add(inst)
    db.commit()
    db.refresh(inst)
    return inst


@router.get("/entities/{entity_id}/instruments", response_model=list[InstrumentOut])
def list_instruments(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(ConvertibleInstrument).filter_by(entity_id=ctx.entity.id).all()


@router.get("/entities/{entity_id}/instruments/execution")
def instruments_execution(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    """Per-instrument execution status: board approval / agreement / e-sign."""
    instruments = db.query(ConvertibleInstrument).filter_by(entity_id=ctx.entity.id).all()
    return svc.execution_status(db, instruments)


@router.post("/instruments/{instrument_id}/agreement", response_model=DocumentOut, status_code=201)
def generate_agreement(
    ctx: InstrumentCtx = Depends(instrument_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    doc = svc.generate_agreement(db, ctx.instrument, user.id)
    return docsvc.document_view(db, doc)


@router.post("/instruments/{instrument_id}/board-approval", response_model=ResolutionOut, status_code=201)
def request_board_approval(
    ctx: InstrumentCtx = Depends(instrument_ctx), db: Session = Depends(get_db)
):
    require_write(ctx.role)
    return svc.request_board_approval(db, ctx.instrument)


@router.get("/instruments/{instrument_id}/conversion-preview")
def conversion_preview(
    round_price_per_share: float,
    ctx: InstrumentCtx = Depends(instrument_ctx),
    db: Session = Depends(get_db),
):
    return svc.conversion_preview(
        db, ctx.instrument, Decimal(str(round_price_per_share)), today_ist()
    )


@router.post("/instruments/{instrument_id}/convert")
def convert_instrument(
    body: InstrumentConvertIn,
    ctx: InstrumentCtx = Depends(instrument_ctx),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    return svc.convert(
        db,
        ctx.instrument,
        body.round_price_per_share,
        body.security_class_id,
        body.conversion_date or today_ist(),
    )


# --- demat / ISIN ---
@router.post("/entities/{entity_id}/demat", response_model=DematOut, status_code=201)
def add_demat(body: DematIn, ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    require_write(ctx.role)
    rec = DematRecord(entity_id=ctx.entity.id, **body.model_dump())
    db.add(rec)
    db.commit()
    db.refresh(rec)
    return rec


@router.get("/entities/{entity_id}/demat", response_model=list[DematOut])
def list_demat(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(DematRecord).filter_by(entity_id=ctx.entity.id).all()


# --- CSV exports ---
def _defuse(cell):
    """Neutralise spreadsheet formula injection: user-entered names starting
    with = + - @ (or tab/CR) would execute as formulas when opened in Excel."""
    if isinstance(cell, str) and cell[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + cell
    return cell


def _csv_response(rows: list[list], filename: str) -> Response:
    buf = io.StringIO()
    csv.writer(buf).writerows([[_defuse(c) for c in row] for row in rows])
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.get("/entities/{entity_id}/cap-table.csv")
def cap_table_csv(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    ct = compute_cap_table(db, ctx.entity.id)
    rows = [["Stakeholder", "Type", "Security", "Quantity", "Invested", "Ownership %"]]
    for h in ct["holders"]:
        rows.append(
            [h["stakeholder_name"], h["stakeholder_type"], h["security_class"], h["quantity"], h["amount_invested"], h["ownership_pct"]]
        )
    return _csv_response(rows, "cap-table.csv")


@router.get("/entities/{entity_id}/compliance.csv")
def compliance_csv(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    obs = db.query(ComplianceObligation).filter_by(entity_id=ctx.entity.id).all()
    today = today_ist()
    rows = [["Form", "Title", "Category", "Period", "Due date", "Status", "Overdue"]]
    for o in obs:
        v = obligation_view(o, today)
        rows.append([v["form_code"], v["title"], v["category"], v["period_label"], v["due_date"], v["status"].value, v["overdue"]])
    return _csv_response(rows, "compliance.csv")

"""Valuation service (FR-L). `current_fmv` returns the FMV from the most
recent final valuation effective as of a date (valuation_date <= as_of and
not expired) — used by ESOP exercise to price the perquisite."""
import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models.valuation import ValuationReport, ValuationStatus


def current_valuation(
    db: Session, entity_id: str, as_of: datetime.date
) -> ValuationReport | None:
    rows = (
        db.query(ValuationReport)
        .filter_by(entity_id=entity_id, status=ValuationStatus.FINAL)
        .filter(ValuationReport.valuation_date <= as_of)
        .order_by(ValuationReport.valuation_date.desc())
        .all()
    )
    for r in rows:
        if r.valid_until is None or r.valid_until >= as_of:
            return r
    return None


def current_fmv(db: Session, entity_id: str, as_of: datetime.date) -> Decimal | None:
    v = current_valuation(db, entity_id, as_of)
    return Decimal(v.fmv_per_share) if v else None

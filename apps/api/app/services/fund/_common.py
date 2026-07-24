"""Shared private helpers used across more than one fund subdomain."""
from decimal import Decimal

from sqlalchemy.orm import Session

from ...models.fund import DrawdownNotice, FeeCharge


def _paid_in_by_lp(db: Session, fund_id: str) -> dict[str, Decimal]:
    rows = db.query(DrawdownNotice).filter_by(fund_id=fund_id, paid=True).all()
    out: dict[str, Decimal] = {}
    for r in rows:
        out[r.lp_id] = out.get(r.lp_id, Decimal("0")) + Decimal(r.amount)
    return out


def _fees_charged_by_lp(db: Session, fund_id: str) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for f in db.query(FeeCharge).filter_by(fund_id=fund_id):
        out[f.lp_id] = out.get(f.lp_id, Decimal("0")) + Decimal(f.amount)
    return out

"""FX translation for cross-border funds: convert a foreign-currency holding
into the fund's reporting currency using the latest dated FxRate on/before a
date. A holding already in the fund currency (or with no rate on file) is left
unchanged, so single-currency funds are unaffected."""
import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from ..models.fund import Fund, FxRate


def rate_for(db: Session, fund_id: str, currency: str, as_of: datetime.date) -> Decimal | None:
    row = (
        db.query(FxRate)
        .filter_by(fund_id=fund_id, currency=currency)
        .filter(FxRate.as_of <= as_of)
        .order_by(FxRate.as_of.desc())
        .first()
    )
    return Decimal(row.rate) if row else None


def translate(db: Session, fund: Fund, amount, currency: str | None, as_of: datetime.date) -> Decimal:
    """Amount (in `currency`) expressed in the fund's currency as of a date."""
    amount = Decimal(amount)
    if not currency or currency == fund.currency:
        return amount
    r = rate_for(db, fund.id, currency, as_of)
    return amount * r if r is not None else amount


def add_rate(db: Session, fund: Fund, currency: str, as_of: datetime.date, rate) -> FxRate:
    row = FxRate(fund_id=fund.id, currency=currency.upper(), as_of=as_of, rate=Decimal(rate))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_rates(db: Session, fund: Fund) -> list[dict]:
    return [
        {"id": r.id, "currency": r.currency, "as_of": r.as_of.isoformat(), "rate": str(r.rate)}
        for r in db.query(FxRate)
        .filter_by(fund_id=fund.id)
        .order_by(FxRate.currency, FxRate.as_of.desc())
    ]

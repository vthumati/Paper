"""Finance service (runway/burn). Runway = latest cash / average monthly burn
over the most recent snapshots."""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..models.finance import FinancialSnapshot

from .money import CENTS  # shared paise quantisation


def runway_summary(db: Session, entity_id: str) -> dict:
    snaps = (
        db.query(FinancialSnapshot)
        .filter_by(entity_id=entity_id)
        .order_by(FinancialSnapshot.period)
        .all()
    )
    rows = [
        {
            "period": s.period,
            "cash_balance": str(s.cash_balance),
            "monthly_burn": str(s.monthly_burn),
            "revenue": str(s.revenue),
        }
        for s in snaps
    ]
    if not snaps:
        return {"snapshots": [], "latest_cash": None, "avg_monthly_burn": None, "runway_months": None}

    latest = snaps[-1]
    recent = snaps[-3:]
    burns = [Decimal(s.monthly_burn) for s in recent if Decimal(s.monthly_burn) > 0]
    avg_burn = (sum(burns) / len(burns)).quantize(CENTS, ROUND_HALF_UP) if burns else Decimal("0")
    runway = (
        float((Decimal(latest.cash_balance) / avg_burn).quantize(Decimal("0.1"), ROUND_HALF_UP))
        if avg_burn > 0
        else None
    )
    return {
        "snapshots": rows,
        "latest_cash": str(latest.cash_balance),
        "latest_revenue": str(latest.revenue),
        "avg_monthly_burn": str(avg_burn),
        "runway_months": runway,
    }

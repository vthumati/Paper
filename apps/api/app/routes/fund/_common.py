import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models.fund import DealActivity, PortfolioInvestment


def _rel_strength(acts: list[DealActivity], today: datetime.date) -> int:
    """0-100 heuristic from logged touches (4Degrees-style, activity-driven):
    frequency (15/touch up to 60) + recency (40 fading to 0 over 6 months)."""
    if not acts:
        return 0
    freq = min(60, len(acts) * 15)
    days = max(0, (today - max(a.occurred_on for a in acts)).days)
    recency = max(0, round(40 * (1 - days / 183)))
    return min(100, freq + recency)


def _get_investment(db: Session, fund_id: str, investment_id: str) -> PortfolioInvestment:
    inv = db.get(PortfolioInvestment, investment_id)
    if inv is None or inv.fund_id != fund_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Investment not found")
    return inv

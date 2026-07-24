"""Fund performance (FR-J-7): the standard LP metrics computed straight from
the drawdown / distribution ledgers plus portfolio marks.

 - paid-in       = sum of paid drawdown notices
 - distributed   = sum of LP distributions (net of carry)
 - NAV           = sum of portfolio marks (current_value, falling back to cost)
                   — a simplification: uninvested fund cash is not tracked
 - DPI  = distributed / paid-in        RVPI = NAV / paid-in
 - TVPI = DPI + RVPI
 - XIRR = money-weighted return over the cashflows (paid drawdowns negative,
   distributions positive, NAV as a terminal inflow today), solved by bisection.
"""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.fund import (
    LP,
    Distribution,
    DrawdownNotice,
    Fund,
    LPDistribution,
    PortfolioInvestment,
    PortfolioValuation,
)
from . import fx
from .money import q

# unitised NAV (FR-J-7): units are issued at a fixed ₹10 par against paid-in
# capital; NAV per unit = portfolio NAV / units outstanding. A simplification —
# real AIF unit accounting issues at prevailing NAV; par-issue keeps units
# proportional to paid-in, which is exact while all LPs pay the same calls.
UNIT_PAR = Decimal("10")


def units_for(paid_in: Decimal) -> Decimal:
    return (paid_in / UNIT_PAR).quantize(Decimal("0.01"))


def management_fee_by_lp(db: Session, fund: Fund, as_of: datetime.date) -> dict[str, Decimal]:
    """Simple (non-compounding) annual fee accrued per LP on the fund's basis:
    'committed' accrues on each LP's commitment from admission;
    'drawn' accrues on each paid drawdown from its payment date."""
    pct = Decimal(fund.mgmt_fee_pct)
    out: dict[str, Decimal] = {}
    if pct <= 0:
        return out
    if fund.fee_basis == "drawn":
        for n in db.query(DrawdownNotice).filter_by(fund_id=fund.id, paid=True):
            days = max(0, (as_of - (n.paid_at or n.created_at).date()).days)
            out[n.lp_id] = out.get(n.lp_id, Decimal("0")) + (
                Decimal(n.amount) * pct * Decimal(days) / Decimal("365")
            )
    else:
        for lp in db.query(LP).filter_by(fund_id=fund.id):
            days = max(0, (as_of - lp.created_at.date()).days)
            out[lp.id] = Decimal(lp.commitment) * pct * Decimal(days) / Decimal("365")
    return out


def management_fee_accrued(db: Session, fund: Fund, as_of: datetime.date) -> Decimal:
    return sum(management_fee_by_lp(db, fund, as_of).values(), Decimal("0"))


def _xirr(cashflows: list[tuple[datetime.date, Decimal]]) -> float | None:
    """Annualised money-weighted return; None if it can't be computed."""
    if len(cashflows) < 2:
        return None
    amounts = [float(a) for _, a in cashflows]
    if all(a >= 0 for a in amounts) or all(a <= 0 for a in amounts):
        return None
    t0 = min(d for d, _ in cashflows)
    times = [(d - t0).days / 365.0 for d, _ in cashflows]

    def npv(rate: float) -> float:
        return sum(a / (1 + rate) ** t for a, t in zip(amounts, times))

    lo, hi = -0.99, 10.0
    if npv(lo) * npv(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if npv(lo) * npv(mid) <= 0:
            hi = mid
        else:
            lo = mid
    return round((lo + hi) / 2 * 100, 2)


def performance_series(db: Session, fund: Fund) -> list[dict]:
    """NAV / DPI / RVPI / TVPI at each ledger-event date — the trend behind the
    headline metrics. Same simplifications as fund_performance; each position
    is valued at its latest valuation or mark dated on or before the point,
    falling back to cost from its investment date."""
    inflows = [
        ((n.paid_at or n.created_at).date(), Decimal(n.amount))
        for n in db.query(DrawdownNotice).filter_by(fund_id=fund.id, paid=True)
    ]
    if not inflows:
        return []
    dist_dates = {
        d.id: d.date or d.created_at.date()
        for d in db.query(Distribution).filter_by(fund_id=fund.id)
    }
    today = today_ist()
    outflows = [
        (dist_dates.get(r.distribution_id, today), Decimal(r.amount))
        for r in db.query(LPDistribution).filter_by(fund_id=fund.id)
    ]

    invs = db.query(PortfolioInvestment).filter_by(fund_id=fund.id).all()
    marks: dict[str, list[tuple[datetime.date, Decimal]]] = {}
    for inv in invs:
        pts = [
            (v.as_of, Decimal(v.value))
            for v in db.query(PortfolioValuation).filter_by(investment_id=inv.id)
        ]
        if inv.current_value is not None and inv.marked_on is not None:
            pts.append((inv.marked_on, Decimal(inv.current_value)))
        marks[inv.id] = sorted(pts)

    dates = {d for d, _ in inflows} | {d for d, _ in outflows} | {today}
    dates |= {inv.invested_on or inv.created_at.date() for inv in invs}
    for pts in marks.values():
        dates |= {d for d, _ in pts}

    def ratio(x: Decimal, paid_in: Decimal) -> str:
        return str((x / paid_in).quantize(Decimal("0.01"), ROUND_HALF_UP))

    series = []
    for t in sorted(dates):
        paid_in = sum((a for d, a in inflows if d <= t), Decimal("0"))
        if paid_in <= 0:
            continue
        distributed = sum((a for d, a in outflows if d <= t), Decimal("0"))
        nav = Decimal("0")
        for inv in invs:
            if (inv.invested_on or inv.created_at.date()) > t:
                continue
            dated = [v for d, v in marks[inv.id] if d <= t]
            native = dated[-1] if dated else Decimal(inv.amount)
            nav += fx.translate(db, fund, native, inv.currency, t)
        series.append(
            {
                "date": t.isoformat(),
                "paid_in": str(q(paid_in)),
                "nav": str(q(nav)),
                "dpi": ratio(distributed, paid_in),
                "rvpi": ratio(nav, paid_in),
                "tvpi": ratio(distributed + nav, paid_in),
            }
        )
    return series


def fund_performance(db: Session, fund: Fund, as_of: datetime.date | None = None) -> dict:
    as_of = as_of or today_ist()

    flows: list[tuple[datetime.date, Decimal]] = []
    paid_in = Decimal("0")
    for n in db.query(DrawdownNotice).filter_by(fund_id=fund.id, paid=True):
        amt = Decimal(n.amount)
        paid_in += amt
        flows.append(((n.paid_at or n.created_at).date(), -amt))

    dist_dates = {d.id: d.date or d.created_at.date() for d in db.query(Distribution).filter_by(fund_id=fund.id)}
    distributed = Decimal("0")
    for r in db.query(LPDistribution).filter_by(fund_id=fund.id):
        amt = Decimal(r.amount)
        distributed += amt
        flows.append((dist_dates.get(r.distribution_id, as_of), amt))

    nav = Decimal("0")
    marked = unmarked = 0
    for p in db.query(PortfolioInvestment).filter_by(fund_id=fund.id):
        # translate a foreign-currency holding to the fund currency (cross-border)
        if p.current_value is not None:
            nav += fx.translate(db, fund, Decimal(p.current_value), p.currency, as_of)
            marked += 1
        else:
            nav += fx.translate(db, fund, Decimal(p.amount), p.currency, as_of)  # at cost
            unmarked += 1
    if nav > 0:
        flows.append((as_of, nav))

    def multiple(x: Decimal) -> str | None:
        return str((x / paid_in).quantize(Decimal("0.01"), ROUND_HALF_UP)) if paid_in > 0 else None

    units = units_for(paid_in)
    nav_per_unit = (
        str((nav / units).quantize(Decimal("0.0001"), ROUND_HALF_UP)) if units > 0 else None
    )
    return {
        "fund_id": fund.id,
        "as_of": as_of,
        "paid_in": str(q(paid_in)),
        "distributed": str(q(distributed)),
        "nav": str(q(nav)),
        "positions_marked": marked,
        "positions_at_cost": unmarked,
        "dpi": multiple(distributed),
        "rvpi": multiple(nav),
        "tvpi": multiple(distributed + nav),
        "xirr_pct": _xirr(flows),
        "management_fee_accrued": str(q(management_fee_accrued(db, fund, as_of))),
        "fee_basis": fund.fee_basis,
        "mgmt_fee_pct": str(fund.mgmt_fee_pct),
        "units_outstanding": str(units),
        "nav_per_unit": nav_per_unit,
    }

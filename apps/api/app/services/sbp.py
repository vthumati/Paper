"""Share-based-payment expense (Ind AS 102 / ICAI Guidance Note on ESOP
accounting): grant-date fair value amortised over the vesting period.

 - options: Black-Scholes grant-date fair value (spot = FMV at grant, plus
   user-supplied volatility, risk-free rate, expected life, dividend yield)
 - RSUs / RSAs: grant-date fair value = full FMV at grant (no exercise cost)

Amortisation is straight-line over the vesting term; per-Indian-financial-year
(Apr–Mar) expense is the difference of cumulative recognition at FY ends.
Simplifications: forfeiture/true-up and graded-vesting per-tranche curves are
not modelled — a defensible MVP for board/audit discussion, not the filing."""
import math
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..models.esop import Grant
from . import fy
from .esop import add_months, months_between
from .money import CENTS
from .valuation import current_fmv


def _norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def black_scholes_call(spot, strike, t_years, vol, rate, div=0.0) -> float:
    """Grant-date fair value of a call option (per unit)."""
    spot, strike, t_years, vol, rate, div = map(float, (spot, strike, t_years, vol, rate, div))
    if t_years <= 0 or vol <= 0 or spot <= 0 or strike <= 0:
        return max(0.0, spot - strike)
    d1 = (math.log(spot / strike) + (rate - div + vol * vol / 2) * t_years) / (vol * math.sqrt(t_years))
    d2 = d1 - vol * math.sqrt(t_years)
    return spot * math.exp(-div * t_years) * _norm_cdf(d1) - strike * math.exp(-rate * t_years) * _norm_cdf(d2)


def grant_fair_value_per_unit(db: Session, grant: Grant, a: dict) -> float | None:
    spot = current_fmv(db, grant.entity_id, grant.grant_date)
    if spot is None:
        return None
    if grant.grant_type in ("rsu", "rsa"):
        return float(spot)
    return black_scholes_call(
        spot, grant.exercise_price, a["expected_life"], a["volatility"], a["risk_free"],
        a.get("dividend_yield", 0.0),
    )


def expense_report(db: Session, entity_id: str, assumptions: dict, as_of) -> dict:
    grants = db.query(Grant).filter_by(entity_id=entity_id).all()
    per_grant = []
    by_fy: dict[str, Decimal] = {}
    total_fv = recognized_to_date = Decimal("0")
    unpriced = 0

    for g in grants:
        fv_unit = grant_fair_value_per_unit(db, g, assumptions)
        if fv_unit is None:
            unpriced += 1
            continue
        total = (Decimal(str(fv_unit)) * g.quantity).quantize(CENTS, ROUND_HALF_UP)
        total_fv += total
        months = max(1, g.total_months)

        def recognized_at(date) -> Decimal:
            m = min(max(months_between(g.grant_date, date), 0), months)
            return (total * m / months).quantize(CENTS, ROUND_HALF_UP)

        recognized_to_date += recognized_at(as_of)
        # spread across financial years by differencing cumulative recognition
        start_y = fy.fy_start_year(g.grant_date)
        full = add_months(g.grant_date, months)
        end_y = fy.fy_start_year(full)
        prev = Decimal("0")
        for y in range(start_y, end_y + 1):
            cum = recognized_at(fy.fy_end_for_start_year(y))
            amt = cum - prev
            prev = cum
            if amt > 0:
                label = fy.fy_label_for_start_year(y)
                by_fy[label] = by_fy.get(label, Decimal("0")) + amt
        per_grant.append(
            {
                "grant_id": g.id,
                "grant_type": g.grant_type,
                "quantity": g.quantity,
                "fair_value_per_unit": str(Decimal(str(fv_unit)).quantize(CENTS, ROUND_HALF_UP)),
                "total_fair_value": str(total),
                "recognized_to_date": str(recognized_at(as_of)),
                "unrecognized": str(total - recognized_at(as_of)),
            }
        )

    schedule = [{"fy": k, "expense": str(v)} for k, v in sorted(by_fy.items())]
    return {
        "as_of": as_of.isoformat(),
        "assumptions": assumptions,
        "grants": per_grant,
        "by_financial_year": schedule,
        "unpriced_grants": unpriced,
        "totals": {
            "total_fair_value": str(total_fv),
            "recognized_to_date": str(recognized_to_date),
            "unrecognized": str(total_fv - recognized_to_date),
        },
    }

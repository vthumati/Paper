"""Shared money/price precision helpers. Money is quantised to paise (2 dp),
per-share prices to 4 dp — used consistently across cap table, fund, ESOP,
instrument and finance computations."""
from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")
PRICE4 = Decimal("0.0001")


def q(x) -> Decimal:
    """Quantise an amount to paise (banker-unfriendly HALF_UP, as used throughout)."""
    return Decimal(x).quantize(CENTS, rounding=ROUND_HALF_UP)


def qp(x) -> Decimal:
    """Quantise a per-share price to 4 decimal places."""
    return Decimal(x).quantize(PRICE4, rounding=ROUND_HALF_UP)

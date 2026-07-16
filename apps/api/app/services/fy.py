"""Indian financial year (Apr–Mar) — the single source of truth for FY math.

A date belongs to the FY that starts in the April on or before it. The label
follows the ROC / tax-statement convention used across compliance and fund
reporting — keyed on the FY-end year, so a date in Apr-2025…Mar-2026 is
"FY2026". Route every "which FY is this / label it" decision through here so
modules never disagree (SEC/quality review H-1).
"""
import datetime


def fy_start_year(d: datetime.date) -> int:
    """Calendar year the FY containing `d` starts in (its April)."""
    return d.year if d.month >= 4 else d.year - 1


def fy_start(d: datetime.date) -> datetime.date:
    """1 April that begins the FY containing `d`."""
    return datetime.date(fy_start_year(d), 4, 1)


def fy_end_for_start_year(start_year: int) -> datetime.date:
    return datetime.date(start_year + 1, 3, 31)


def fy_end(d: datetime.date) -> datetime.date:
    """31 March that ends the FY containing `d`."""
    return fy_end_for_start_year(fy_start_year(d))


def fy_label_for_start_year(start_year: int) -> str:
    return f"FY{start_year + 1}"


def fy_label(d: datetime.date) -> str:
    """Label for the FY containing `d`: Apr-2025…Mar-2026 → 'FY2026'."""
    return fy_label_for_start_year(fy_start_year(d))

"""Statutory obligation rules as data (ADR-3). Due dates are derived from the
financial-year end. Defaults assume a 31-March FY (the common Indian case);
the due (month, day) are calendar dates in the FY-end year unless year_offset
shifts them. Validate against current law before production use."""
import datetime
from dataclasses import dataclass


@dataclass(frozen=True)
class ObligationRule:
    form_code: str
    title: str
    category: str
    due_month: int
    due_day: int
    year_offset: int = 0


# Annual ROC / tax obligations for a private limited company (31-March FY).
RULES: list[ObligationRule] = [
    ObligationRule("DPT-3", "Return of deposits (DPT-3)", "ROC", 6, 30),
    ObligationRule("DIR-3 KYC", "Director KYC (DIR-3 KYC)", "ROC", 9, 30),
    ObligationRule("ADT-1", "Auditor appointment (ADT-1)", "ROC", 10, 14),
    ObligationRule("AOC-4", "Financial statements (AOC-4)", "ROC", 10, 30),
    ObligationRule("MGT-7", "Annual return (MGT-7)", "ROC", 11, 29),
]


def due_date_for(rule: ObligationRule, fy_end: datetime.date) -> datetime.date:
    return datetime.date(fy_end.year + rule.year_offset, rule.due_month, rule.due_day)

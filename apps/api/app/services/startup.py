"""Startup India / DPIIT service (FR-B-6): eligibility check from entity facts
and gating of tax-benefit applications on DPIIT recognition."""
import datetime

from ..models.entity import LegalEntity

ELIGIBLE_TYPES = {"pvt_ltd", "llp"}
MAX_AGE_YEARS = 10


def eligibility(entity: LegalEntity, today: datetime.date) -> dict:
    reasons = []
    eligible = True

    if entity.type.value not in ELIGIBLE_TYPES:
        eligible = False
        reasons.append("Entity must be a Private Limited Company or LLP for DPIIT recognition.")
    else:
        reasons.append("Entity type is eligible (Pvt Ltd / LLP).")

    if entity.incorporation_date is None:
        reasons.append("Set the incorporation date to confirm the 10-year age criterion.")
    else:
        years = (today - entity.incorporation_date).days / 365.25
        if years > MAX_AGE_YEARS:
            eligible = False
            reasons.append(f"Incorporated {years:.1f} years ago — exceeds the 10-year limit.")
        else:
            reasons.append(f"Within the 10-year age limit ({years:.1f} years).")

    reasons.append("Turnover must be under ₹100 crore in any financial year (not tracked here).")
    return {"eligible": eligible, "entity_type": entity.type.value, "reasons": reasons}

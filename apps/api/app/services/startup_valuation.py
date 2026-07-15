"""Self-serve indicative startup valuation (FR-L-2, Eqvista-style).

Three methods computed from founder inputs, blended by custom weights:
 - scorecard: benchmark pre-money × weighted factor scores (pre-revenue)
 - vc_method: exit value / target multiple − planned raise
 - dcf:       discounted free cash flows from a revenue/expense projection

All of it is rules-as-data (the scorecard factor registry below) and pure
arithmetic — indicative only, a supporting workpaper for a Rule 11UA
engagement, never a registered-valuer report (the disclaimer travels with
every result). `smartfill` pre-fills a DCF projection from the entity's
financial snapshots so founders start from their own numbers."""
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.entity import LegalEntity
from ..models.finance import FinancialSnapshot
from ..models.valuation import ValuationEstimate
from . import document as docsvc
from .diluted import fully_diluted
from .money import CENTS

_METHOD_LABEL = {
    "scorecard": "Scorecard",
    "vc_method": "VC method",
    "dcf": "Discounted cash flow",
}

# Bill Payne scorecard weights — the market-standard factor mix.
SCORECARD_FACTORS = [
    {"key": "team", "label": "Strength of the team", "weight": Decimal("0.30")},
    {"key": "opportunity", "label": "Size of the opportunity", "weight": Decimal("0.25")},
    {"key": "product", "label": "Product / technology", "weight": Decimal("0.15")},
    {"key": "competition", "label": "Competitive environment", "weight": Decimal("0.10")},
    {"key": "sales", "label": "Marketing & sales channels", "weight": Decimal("0.10")},
    {"key": "funding_need", "label": "Need for additional funding", "weight": Decimal("0.05")},
    {"key": "other", "label": "Other factors", "weight": Decimal("0.05")},
]

DISCLAIMER = (
    "Indicative valuation computed from founder inputs. Not a report by a "
    "registered valuer or merchant banker — use as a supporting workpaper for "
    "a Rule 11UA / FEMA valuation engagement."
)


def _scorecard(inputs: dict) -> Decimal:
    base = Decimal(str(inputs["base_valuation"]))
    scores = inputs.get("scores", {})
    factor = sum(
        f["weight"] * Decimal(str(scores.get(f["key"], 100))) / Decimal("100")
        for f in SCORECARD_FACTORS
    )
    return (base * factor).quantize(CENTS, ROUND_HALF_UP)


def _vc_method(inputs: dict) -> dict:
    exit_value = Decimal(str(inputs["exit_value"]))
    multiple = Decimal(str(inputs["target_multiple"]))
    raise_amt = Decimal(str(inputs.get("planned_raise", 0)))
    post = (exit_value / multiple).quantize(CENTS, ROUND_HALF_UP)
    pre = post - raise_amt
    if pre <= 0:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "VC method: the planned raise exceeds the implied post-money",
        )
    return {"post_money": post, "pre_money": pre}


def _dcf(inputs: dict) -> Decimal:
    projections = inputs["projections"]
    r = Decimal(str(inputs["discount_rate_pct"])) / Decimal("100")
    g = Decimal(str(inputs.get("terminal_growth_pct", 0))) / Decimal("100")
    if r <= g:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "DCF: the discount rate must exceed the terminal growth rate",
        )
    value = Decimal("0")
    fcf = Decimal("0")
    for t, p in enumerate(projections, start=1):
        fcf = Decimal(str(p["revenue"])) - Decimal(str(p["expenses"]))
        value += fcf / (Decimal("1") + r) ** t
    if fcf > 0:  # terminal value only off a positive final-year cash flow
        terminal = fcf * (Decimal("1") + g) / (r - g)
        value += terminal / (Decimal("1") + r) ** len(projections)
    return value.quantize(CENTS, ROUND_HALF_UP)


def compute_estimate(db: Session, entity_id: str, body) -> dict:
    """Run every method the founder supplied inputs for, blend by weights,
    and translate to a per-share value on the fully-diluted count."""
    values: dict[str, Decimal] = {}
    detail: dict[str, dict] = {}
    if body.scorecard is not None:
        values["scorecard"] = _scorecard(body.scorecard.model_dump(mode="json"))
    if body.vc_method is not None:
        vc = _vc_method(body.vc_method.model_dump(mode="json"))
        values["vc_method"] = vc["pre_money"]
        detail["vc_method"] = {k: str(v) for k, v in vc.items()}
    if body.dcf is not None:
        values["dcf"] = _dcf(body.dcf.model_dump(mode="json"))

    weights = {m: Decimal(str(w)) for m, w in body.weights.items() if Decimal(str(w)) > 0}
    unknown = set(weights) - {"scorecard", "vc_method", "dcf"}
    if unknown:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Unknown methods: {sorted(unknown)}")
    missing = set(weights) - set(values)
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Weighted methods missing inputs: {sorted(missing)}",
        )
    if not weights:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "At least one method needs weight > 0")

    total_w = sum(weights.values())
    normalized = {m: w / total_w for m, w in weights.items()}
    blended = sum(values[m] * w for m, w in normalized.items()).quantize(CENTS, ROUND_HALF_UP)

    # structure probe (price-independent), same basis as scenario modelling
    fd = fully_diluted(db, entity_id, Decimal("1"))
    fd_shares = fd["issued_shares"] + fd["option_shares"] + fd["pool_unallocated"]
    per_share = (
        (blended / fd_shares).quantize(Decimal("0.0001"), ROUND_HALF_UP)
        if fd_shares > 0 and blended > 0
        else None
    )

    return {
        "methods": {m: str(v) for m, v in values.items()},
        "detail": detail,
        "weights": {m: str(w.quantize(Decimal("0.0001"))) for m, w in normalized.items()},
        "blended_value": str(blended),
        "fd_shares": fd_shares,
        "per_share": str(per_share) if per_share is not None else None,
        "disclaimer": DISCLAIMER,
    }


def smartfill(db: Session, entity_id: str, growth_pct: Decimal, years: int = 5) -> dict:
    """Pre-fill a DCF projection from the entity's financial snapshots:
    annualised revenue and expenses (burn is net, so expenses = burn + revenue)
    grown at `growth_pct`, with expenses growing at half that rate (a simple
    operating-leverage assumption the founder can edit)."""
    snaps = (
        db.query(FinancialSnapshot)
        .filter_by(entity_id=entity_id)
        .order_by(FinancialSnapshot.period.desc())
        .limit(12)
        .all()
    )
    if not snaps:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No financial snapshots to smartfill from — add monthly financials first",
        )
    n = len(snaps)
    avg_rev = sum(Decimal(s.revenue) for s in snaps) / n
    avg_burn = sum(Decimal(s.monthly_burn) for s in snaps) / n
    annual_rev = avg_rev * 12
    annual_exp = (avg_burn + avg_rev) * 12

    g = growth_pct / Decimal("100")
    rows = []
    rev, exp = annual_rev, annual_exp
    for year in range(1, years + 1):
        rev = rev * (Decimal("1") + g)
        exp = exp * (Decimal("1") + g / 2)
        rows.append(
            {
                "year": year,
                "revenue": str(rev.quantize(CENTS, ROUND_HALF_UP)),
                "expenses": str(exp.quantize(CENTS, ROUND_HALF_UP)),
            }
        )
    return {
        "base_annual_revenue": str(annual_rev.quantize(CENTS, ROUND_HALF_UP)),
        "base_annual_expenses": str(annual_exp.quantize(CENTS, ROUND_HALF_UP)),
        "assumed_growth_pct": str(growth_pct),
        "months_of_data": n,
        "projections": rows,
    }


def generate_report(db: Session, estimate: ValuationEstimate, user_id: str):
    """Render a saved estimate as an indicative valuation workpaper document."""
    r = estimate.results
    entity = db.get(LegalEntity, estimate.entity_id)
    method_lines = "\n".join(
        f"  {_METHOD_LABEL.get(m, m)}: ₹{v}" for m, v in r.get("methods", {}).items()
    )
    weight_str = ", ".join(
        f"{_METHOD_LABEL.get(m, m)} {Decimal(w) * 100:.1f}%"
        for m, w in r.get("weights", {}).items()
    )
    return docsvc.create_document(
        db,
        entity_id=estimate.entity_id,
        template_key="valuation_estimate",
        data={
            "company": entity.name if entity else "",
            "label": estimate.label,
            "date": estimate.created_at.date().isoformat(),
            "methods": "Method values:\n" + method_lines if method_lines else "",
            "weights": weight_str,
            "blended_value": r.get("blended_value", ""),
            "fd_shares": f"{r.get('fd_shares', 0):,}",
            "per_share": r.get("per_share") or "n/a",
            "disclaimer": r.get("disclaimer", DISCLAIMER),
        },
        user_id=user_id,
        title=f"Indicative valuation — {estimate.label}",
        subject_type="valuation_estimate",
        subject_id=estimate.id,
    )

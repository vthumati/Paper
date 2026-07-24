"""Money movement & financials: capital calls, distributions/waterfall, fees,
fund financial statements, expense ledger, follow-on rounds and fund
construction/forecast.

Profit distributions follow a cumulative European waterfall (FR-J-5):
1. return of capital until LPs have received total paid-in,
2. preferred return (`hurdle_pct`, simple, accrued on each paid drawdown from
   its payment date to the distribution date),
3. 100% GP catch-up until the GP holds `carry_pct` of profits,
4. remainder split `carry_pct` GP / rest LPs.
The tiers are recomputed over cumulative totals each time, so the GP take of
any one distribution is the cumulative GP target minus GP already paid.
Simplification: pref keeps accruing on all paid-in capital (earlier return-of-
capital distributions don't stop the clock)."""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...clock import now_ist, today_ist
from ...models.fund import (
    CapitalCall,
    Distribution,
    DistributionKind,
    DrawdownNotice,
    FeeCharge,
    Fund,
    FundExpense,
    FundPlan,
    InvestmentRound,
    LP,
    LPDistribution,
    PortfolioInvestment,
)
from ..fund_perf import management_fee_by_lp
from ..money import q  # shared paise quantisation
from ._common import _fees_charged_by_lp, _paid_in_by_lp


def create_capital_call(
    db: Session, fund: Fund, pct: Decimal, purpose: str | None, due_date: datetime.date | None
) -> CapitalCall:
    if pct <= 0 or pct > 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "pct must be in (0, 1]")
    lps = db.query(LP).filter_by(fund_id=fund.id).all()
    if not lps:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Fund has no LPs to call")
    n = db.query(CapitalCall).filter_by(fund_id=fund.id).count()
    call = CapitalCall(
        fund_id=fund.id, call_no=n + 1, pct=pct, purpose=purpose, due_date=due_date
    )
    db.add(call)
    db.flush()
    for lp in lps:
        db.add(
            DrawdownNotice(
                call_id=call.id,
                fund_id=fund.id,
                lp_id=lp.id,
                amount=q(Decimal(lp.commitment) * pct),
                paid=False,
            )
        )
    db.commit()
    db.refresh(call)
    return call


def mark_paid(
    db: Session, notice: DrawdownNotice, payment_ref: str | None = None, verified_by: str | None = None
) -> DrawdownNotice:
    """Verify a drawdown payment: records receipt, the remittance reference (UTR)
    and who confirmed it. Idempotent on `paid`, but a later call can still attach
    the reference."""
    if not notice.paid:
        notice.paid = True
        # IST, same frame as today_ist(): pref accrual compares this date
        # against distribution dates — a mixed-timezone date can be a day off
        notice.paid_at = now_ist()
    if payment_ref:
        notice.payment_ref = payment_ref
    if verified_by:
        notice.verified_by = verified_by
    db.commit()
    db.refresh(notice)
    return notice


def _bank_block(fund: Fund) -> str:
    if fund.bank_account:
        return (
            f"  Bank: {fund.bank_name or '—'}\n"
            f"  Account: {fund.bank_account}\n"
            f"  IFSC: {fund.bank_ifsc or '—'}"
        )
    return "  Bank details to follow from the fund administrator."


def generate_drawdown_notice(db: Session, notice: DrawdownNotice, user_id: str):
    """Generate the LP's drawdown-notice document with remittance details."""
    from ...models.entity import LegalEntity
    from .. import document as docsvc

    fund = db.get(Fund, notice.fund_id)
    lp = db.get(LP, notice.lp_id)
    call = db.get(CapitalCall, notice.call_id)
    entity = db.get(LegalEntity, fund.entity_id) if fund else None
    purpose = f" ({call.purpose})" if call and call.purpose else ""
    due = call.due_date.isoformat() if call and call.due_date else "on receipt"
    return docsvc.create_document(
        db,
        entity_id=fund.entity_id,
        template_key="drawdown_notice",
        data={
            "fund": entity.name if entity else "",
            "lp": lp.name if lp else "",
            "date": today_ist().isoformat(),
            "call_no": call.call_no if call else "",
            "amount": str(q(notice.amount)),
            "purpose_line": purpose,
            "due_date": due,
            "bank": _bank_block(fund),
        },
        user_id=user_id,
        title=f"Drawdown Notice — Call {call.call_no if call else ''} — {lp.name if lp else ''}",
        subject_type="drawdown_notice",
        subject_id=notice.id,
    )


def lp_distribution_history(db: Session, fund_id: str, lp_id: str) -> list[dict]:
    """Per-LP distribution history: each distribution this LP received a slice of."""
    dists = {d.id: d for d in db.query(Distribution).filter_by(fund_id=fund_id)}
    out = []
    for r in db.query(LPDistribution).filter_by(fund_id=fund_id, lp_id=lp_id):
        d = dists.get(r.distribution_id)
        if d is None:
            continue
        out.append({
            "dist_no": d.dist_no,
            "date": d.date.isoformat() if d.date else None,
            "kind": d.kind.value,
            "amount": str(q(r.amount)),
        })
    out.sort(key=lambda x: x["dist_no"])
    return out


def generate_audited_financials(db: Session, fund: Fund, auditor_name: str, user_id: str):
    """An audited-financials document built from the fund's financial statements."""
    from ...models.entity import LegalEntity
    from .. import document as docsvc

    fin = fund_financials(db, fund)
    entity = db.get(LegalEntity, fund.entity_id)
    bs, ops, roll = fin["balance_sheet"], fin["operations"], fin["capital_roll_forward"]
    return docsvc.create_document(
        db,
        entity_id=fund.entity_id,
        template_key="audited_financials",
        data={
            "fund": entity.name if entity else "",
            "date": fin["as_of"].isoformat(),
            "auditor": auditor_name,
            "investments_fv": bs["investments_at_fair_value"],
            "cash": bs["cash"],
            "total_assets": bs["total_assets"],
            "net_assets": bs["net_assets"],
            "net_ops": ops["net_increase_from_operations"],
            "contributions": roll["contributions"],
            "dist_lps": roll["distributions_to_lps"].lstrip("-"),
            "carry": roll["carry_to_gp"].lstrip("-"),
        },
        user_id=user_id,
        title=f"Audited Financials — {entity.name if entity else ''}",
        subject_type="audited_financials",
        subject_id=fund.id,
    )


def _waterfall_tiers(
    total: Decimal, paid_in: Decimal, accrued_pref: Decimal, carry_pct: Decimal
) -> dict[str, Decimal]:
    """Split a cumulative distributed total into waterfall tiers."""
    roc = min(total, paid_in)
    rem = total - roc
    pref = min(rem, accrued_pref)
    rem -= pref
    # 100% catch-up: GP takes all of tier 3 until GP = carry_pct of profits,
    # i.e. catch-up target = pref × carry / (1 − carry)
    catchup_target = pref * carry_pct / (Decimal("1") - carry_pct) if carry_pct < 1 else rem
    catchup = min(rem, catchup_target)
    rem -= catchup
    return {"roc": roc, "pref": pref, "catchup": catchup, "gp": catchup + rem * carry_pct}


def _accrued_pref(db: Session, fund: Fund, as_of: datetime.date) -> Decimal:
    total = Decimal("0")
    for n in db.query(DrawdownNotice).filter_by(fund_id=fund.id, paid=True):
        start = (n.paid_at or n.created_at).date()
        days = max(0, (as_of - start).days)
        total += Decimal(n.amount) * Decimal(fund.hurdle_pct) * Decimal(days) / Decimal("365")
    return total


def record_distribution(
    db: Session,
    fund: Fund,
    gross: Decimal,
    kind: DistributionKind,
    dist_date: datetime.date | None = None,
) -> Distribution:
    if gross <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "gross_amount must be positive")
    dist_date = dist_date or today_ist()
    lps = db.query(LP).filter_by(fund_id=fund.id).all()
    paid_in = _paid_in_by_lp(db, fund.id)

    carry = roc_amt = pref_amt = catchup_amt = Decimal("0")
    if kind == DistributionKind.RETURN_OF_CAPITAL:
        roc_amt = q(Decimal(gross))
    else:
        paid_in_total = sum(paid_in.values(), Decimal("0"))
        accrued_pref = _accrued_pref(db, fund, dist_date)
        prior_lp = sum(
            (Decimal(r.amount) for r in db.query(LPDistribution).filter_by(fund_id=fund.id)),
            Decimal("0"),
        )
        prior_gp = sum(
            (Decimal(d.carry_amount) for d in db.query(Distribution).filter_by(fund_id=fund.id)),
            Decimal("0"),
        )
        cum_prev = prior_lp + prior_gp
        carry_pct = Decimal(fund.carry_pct)
        prev = _waterfall_tiers(cum_prev, paid_in_total, accrued_pref, carry_pct)
        now = _waterfall_tiers(cum_prev + Decimal(gross), paid_in_total, accrued_pref, carry_pct)
        # cumulative GP target minus GP already paid, clamped to this gross
        carry = q(min(max(now["gp"] - prior_gp, Decimal("0")), Decimal(gross)))
        roc_amt = q(now["roc"] - prev["roc"])
        pref_amt = q(now["pref"] - prev["pref"])
        catchup_amt = q(now["catchup"] - prev["catchup"])
    net = q(Decimal(gross) - carry)

    # weights: paid-in capital; fall back to commitments if nothing drawn yet
    weights = {lp.id: paid_in.get(lp.id, Decimal("0")) for lp in lps}
    total = sum(weights.values())
    if total == 0:
        weights = {lp.id: Decimal(lp.commitment) for lp in lps}
        total = sum(weights.values())
    if total == 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Fund has no LP basis to distribute")

    n = db.query(Distribution).filter_by(fund_id=fund.id).count()
    dist = Distribution(
        fund_id=fund.id,
        dist_no=n + 1,
        gross_amount=q(Decimal(gross)),
        kind=kind,
        carry_amount=carry,
        roc_amount=roc_amt,
        pref_amount=pref_amt,
        catchup_amount=catchup_amt,
        date=dist_date,
    )
    db.add(dist)
    db.flush()

    # allocate net pro-rata; last LP absorbs the rounding remainder
    allocated = Decimal("0")
    for i, lp in enumerate(lps):
        if i == len(lps) - 1:
            amt = q(net - allocated)
        else:
            amt = q(net * weights[lp.id] / total)
            allocated += amt
        db.add(LPDistribution(distribution_id=dist.id, fund_id=fund.id, lp_id=lp.id, amount=amt))
    db.commit()
    db.refresh(dist)
    return dist


def charge_fees(db: Session, fund: Fund, as_of: datetime.date) -> dict:
    """Crystallise the management fee: charge each LP the fee accrued to
    `as_of` minus what has already been charged. Append-only and therefore
    safe to run repeatedly (a second run the same day charges nothing)."""
    # resolve via the package namespace so tests patching
    # `app.services.fund.today_ist` still take effect (as with the old module)
    from . import today_ist

    as_of = min(as_of, today_ist())  # never charge fees that haven't accrued yet
    accrued = management_fee_by_lp(db, fund, as_of)
    already = _fees_charged_by_lp(db, fund.id)
    charges = []
    for lp_id, acc in accrued.items():
        due = q(acc) - already.get(lp_id, Decimal("0"))
        if due <= 0:
            continue
        fc = FeeCharge(
            fund_id=fund.id,
            lp_id=lp_id,
            amount=due,
            period_label=f"to {as_of.isoformat()}",
            charged_on=as_of,
        )
        db.add(fc)
        charges.append({"lp_id": lp_id, "amount": str(due)})
    db.commit()
    return {
        "charged": str(q(sum((Decimal(c["amount"]) for c in charges), Decimal("0")))),
        "charges": charges,
    }


# --- fund construction / forecast (Carta "Fund Forecasting") -----------------
def get_or_default_plan(db: Session, fund: Fund) -> tuple[FundPlan | None, bool]:
    """Return (plan, has_plan). When no plan is saved yet, returns None so the
    caller computes with defaults seeded from the fund."""
    plan = db.query(FundPlan).filter_by(fund_id=fund.id).first()
    return plan, plan is not None


def upsert_plan(db: Session, fund: Fund, data: dict) -> FundPlan:
    plan = db.query(FundPlan).filter_by(fund_id=fund.id).first()
    if plan is None:
        plan = FundPlan(fund_id=fund.id)
        db.add(plan)
    for k, v in data.items():
        setattr(plan, k, v)
    db.commit()
    db.refresh(plan)
    return plan


def compute_plan(db: Session, fund: Fund) -> dict:
    """Portfolio-construction model + projected returns + deployment pacing,
    with plan-vs-actual read live from the portfolio and LP ledgers.

    Simplifications (all clearly a planning model, not GAAP):
      lifetime fees = mgmt_fee_pct × fund_size × fund_life  (no step-down)
      investable    = fund_size − lifetime fees − expenses
      reserves      = investable × reserve_pct;  initial = investable − reserves
      gross proceeds = investable × projected_gross_moic
      GP carry      = carry_pct × profit over committed  (hurdle ignored here)
      net IRR       ≈ net_tvpi ^ (1 / (0.6 × life)) − 1   (rough, timing-free)
    """
    plan, has_plan = get_or_default_plan(db, fund)

    size = Decimal(plan.fund_size) if plan else Decimal(fund.target_corpus or 0)
    life = plan.fund_life_years if plan else 10
    inv_period = min(plan.investment_period_years if plan else 4, life or 1)
    expenses = Decimal(plan.est_expenses) if plan else Decimal("0")
    reserve_pct = Decimal(plan.reserve_pct) if plan else Decimal("0.40")
    cheque = Decimal(plan.avg_initial_cheque) if plan else Decimal("0")
    entry_val = Decimal(plan.avg_entry_valuation) if plan else Decimal("0")
    moic = Decimal(plan.projected_gross_moic) if plan else Decimal("3")
    fee_pct = Decimal(fund.mgmt_fee_pct)
    carry_pct = Decimal(fund.carry_pct)

    lifetime_fees = fee_pct * size * Decimal(life)
    investable = size - lifetime_fees - expenses
    if investable < 0:
        investable = Decimal("0")
    reserve_capital = investable * reserve_pct
    initial_capital = investable - reserve_capital
    num_deals = int(initial_capital / cheque) if cheque > 0 else 0
    avg_own = (cheque / entry_val * Decimal("100")) if entry_val > 0 else Decimal("0")

    gross_proceeds = investable * moic
    profit = gross_proceeds - size
    if profit < 0:
        profit = Decimal("0")
    gp_carry = carry_pct * profit
    net_to_lps = gross_proceeds - gp_carry
    gross_tvpi = (gross_proceeds / size) if size > 0 else None
    net_tvpi = (net_to_lps / size) if size > 0 else None

    net_irr = None
    if net_tvpi and net_tvpi > 0:
        avg_hold = max(1.0, float(life) * 0.6)
        net_irr = round((float(net_tvpi) ** (1.0 / avg_hold) - 1.0) * 100, 1)

    # deployment pacing: initial + reserves spread evenly across the period
    initial_per_year = initial_capital / inv_period if inv_period else Decimal("0")
    reserve_per_year = reserve_capital / inv_period if inv_period else Decimal("0")
    pacing = []
    cum = Decimal("0")
    for yr in range(1, inv_period + 1):
        deployed = initial_per_year + reserve_per_year
        cum += deployed
        pacing.append({
            "year": yr,
            "initial": str(q(initial_per_year)),
            "reserve": str(q(reserve_per_year)),
            "deployed": str(q(deployed)),
            "cumulative": str(q(cum)),
        })

    # plan vs actual, live from the ledgers
    deployed_actual = sum(
        (Decimal(p.amount) for p in db.query(PortfolioInvestment).filter_by(fund_id=fund.id)),
        Decimal("0"),
    )
    deals_actual = db.query(PortfolioInvestment).filter_by(fund_id=fund.id).count()
    committed_actual = sum(
        (Decimal(lp.commitment) for lp in db.query(LP).filter_by(fund_id=fund.id)),
        Decimal("0"),
    )

    def pct_of(part: Decimal, whole: Decimal) -> float | None:
        return round(float(part / whole * 100), 1) if whole > 0 else None

    # variance report: plan vs the live ledgers, row per comparable metric
    from ..fund_perf import fund_performance as _perf

    investments = db.query(PortfolioInvestment).filter_by(fund_id=fund.id).all()
    avg_cheque_actual = (
        deployed_actual / len(investments) if investments else Decimal("0")
    )
    fv_total = sum(
        (Decimal(p.current_value if p.current_value is not None else p.amount) for p in investments),
        Decimal("0"),
    )
    moic_actual = (fv_total / deployed_actual) if deployed_actual > 0 else None
    perf = _perf(db, fund)
    tvpi_actual = Decimal(perf["tvpi"]) if perf["tvpi"] else None

    # planned deployment to date: pacing years elapsed since the first investment
    first_dates = [p.invested_on for p in investments if p.invested_on]
    planned_to_date = None
    if first_dates and inv_period:
        elapsed_years = min(
            inv_period, max(1, (today_ist() - min(first_dates)).days // 365 + 1)
        )
        planned_to_date = (investable / inv_period) * elapsed_years

    def _variance(planned, actual) -> float | None:
        if planned is None or actual is None or Decimal(str(planned)) == 0:
            return None
        return round(float((Decimal(str(actual)) - Decimal(str(planned))) / Decimal(str(planned)) * 100), 1)

    variance = [
        {"metric": "Committed capital", "unit": "inr",
         "planned": str(q(size)), "actual": str(q(committed_actual)),
         "variance_pct": _variance(size, committed_actual)},
        {"metric": "Capital deployed to date", "unit": "inr",
         "planned": str(q(planned_to_date)) if planned_to_date is not None else None,
         "actual": str(q(deployed_actual)),
         "variance_pct": _variance(planned_to_date, deployed_actual)},
        {"metric": "Average initial cheque", "unit": "inr",
         "planned": str(q(cheque)) if cheque > 0 else None,
         "actual": str(q(avg_cheque_actual)) if investments else None,
         "variance_pct": _variance(cheque if cheque > 0 else None,
                                   avg_cheque_actual if investments else None)},
        {"metric": "Portfolio companies", "unit": "number",
         "planned": num_deals or None, "actual": deals_actual,
         "variance_pct": _variance(num_deals or None, deals_actual)},
        {"metric": "Gross MOIC", "unit": "x",
         "planned": str(moic),
         "actual": str(moic_actual.quantize(Decimal("0.01"), ROUND_HALF_UP)) if moic_actual is not None else None,
         "variance_pct": _variance(moic, moic_actual)},
        {"metric": "Net TVPI", "unit": "x",
         "planned": str(net_tvpi.quantize(Decimal("0.01"), ROUND_HALF_UP)) if net_tvpi else None,
         "actual": str(tvpi_actual) if tvpi_actual is not None else None,
         "variance_pct": _variance(net_tvpi, tvpi_actual)},
    ]

    return {
        "has_plan": has_plan,
        "inputs": {
            "fund_size": str(q(size)),
            "fund_life_years": life,
            "investment_period_years": inv_period,
            "est_expenses": str(q(expenses)),
            "reserve_pct": str(reserve_pct),
            "avg_initial_cheque": str(q(cheque)),
            "avg_entry_valuation": str(q(entry_val)),
            "projected_gross_moic": str(moic),
            "mgmt_fee_pct": str(fee_pct),
            "carry_pct": str(carry_pct),
        },
        "derived": {
            "lifetime_fees": str(q(lifetime_fees)),
            "investable": str(q(investable)),
            "initial_capital": str(q(initial_capital)),
            "reserve_capital": str(q(reserve_capital)),
            "num_initial_deals": num_deals,
            "avg_entry_ownership_pct": str(avg_own.quantize(Decimal("0.01"), ROUND_HALF_UP)),
            "gross_proceeds": str(q(gross_proceeds)),
            "gp_carry": str(q(gp_carry)),
            "net_to_lps": str(q(net_to_lps)),
            "gross_tvpi": str(gross_tvpi.quantize(Decimal("0.01"), ROUND_HALF_UP)) if gross_tvpi else None,
            "net_tvpi": str(net_tvpi.quantize(Decimal("0.01"), ROUND_HALF_UP)) if net_tvpi else None,
            "net_irr_pct": net_irr,
        },
        "pacing": pacing,
        "actual": {
            "committed": str(q(committed_actual)),
            "deployed": str(q(deployed_actual)),
            "deals": deals_actual,
            "committed_vs_target_pct": pct_of(committed_actual, size),
            "deployed_vs_initial_pct": pct_of(deployed_actual, initial_capital),
            "deals_vs_plan_pct": round(deals_actual / num_deals * 100, 1) if num_deals else None,
        },
        "variance": variance,
    }


# --- fund financial statements (Carta "fund accounting", no GL export) --------
def fund_financials(db: Session, fund: Fund) -> dict:
    """Since-inception fund financial statements derived from the existing
    ledgers — statement of operations, cash flows, assets & liabilities, and a
    partners'-capital roll-forward that ties to net assets by construction.

    Simplifications (a fund-accounting *view*, not audited GAAP): cash is a
    derived plug (contributions − investments at cost − distributions − carry −
    fees), not a real bank ledger; there are no accrued liabilities; realised
    gains aren't tracked separately from unrealised marks; and management fee is
    assumed paid out when charged."""
    paid_in = sum(
        (Decimal(n.amount) for n in db.query(DrawdownNotice).filter_by(fund_id=fund.id, paid=True)),
        Decimal("0"),
    )
    invested_cost = Decimal("0")
    investments_fv = Decimal("0")
    positions_at_cost = 0
    for p in db.query(PortfolioInvestment).filter_by(fund_id=fund.id):
        invested_cost += Decimal(p.amount)
        if p.current_value is not None:
            investments_fv += Decimal(p.current_value)
        else:
            investments_fv += Decimal(p.amount)
            positions_at_cost += 1
    unrealized = investments_fv - invested_cost
    fees = sum(
        (Decimal(f.amount) for f in db.query(FeeCharge).filter_by(fund_id=fund.id)), Decimal("0")
    )
    distributed_lps = sum(
        (Decimal(r.amount) for r in db.query(LPDistribution).filter_by(fund_id=fund.id)),
        Decimal("0"),
    )
    carry = sum(
        (Decimal(d.carry_amount) for d in db.query(Distribution).filter_by(fund_id=fund.id)),
        Decimal("0"),
    )
    committed = sum(
        (Decimal(lp.commitment) for lp in db.query(LP).filter_by(fund_id=fund.id)), Decimal("0")
    )
    expenses = sum(
        (Decimal(e.amount) for e in db.query(FundExpense).filter_by(fund_id=fund.id)),
        Decimal("0"),
    )

    net_operations = unrealized - fees - expenses  # = statement-of-operations bottom line
    cash = paid_in - invested_cost - distributed_lps - carry - fees - expenses
    net_assets = investments_fv + cash
    ending_capital = paid_in + net_operations - distributed_lps - carry

    s = lambda x: str(q(x))  # noqa: E731 (local money formatter)
    return {
        "fund_id": fund.id,
        "as_of": today_ist(),
        "operations": {
            "realized_gains": s(Decimal("0")),
            "unrealized_appreciation": s(unrealized),
            "total_investment_income": s(unrealized),
            "management_fees": s(fees),
            "fund_expenses": s(expenses),
            "net_increase_from_operations": s(net_operations),
        },
        "cash_flow": {
            "contributions": s(paid_in),
            "investments_made": s(-invested_cost),
            "distributions_to_lps": s(-distributed_lps),
            "carry_paid": s(-carry),
            "management_fees_paid": s(-fees),
            "fund_expenses_paid": s(-expenses),
            "net_change_in_cash": s(cash),
            "ending_cash": s(cash),
        },
        "balance_sheet": {
            "investments_at_fair_value": s(investments_fv),
            "cash": s(cash),
            "total_assets": s(investments_fv + cash),
            "liabilities": s(Decimal("0")),
            "net_assets": s(net_assets),
        },
        "capital_roll_forward": {
            "beginning": s(Decimal("0")),
            "contributions": s(paid_in),
            "net_increase_from_operations": s(net_operations),
            "distributions_to_lps": s(-distributed_lps),
            "carry_to_gp": s(-carry),
            "ending_net_assets": s(ending_capital),
        },
        "disclosures": {
            "committed": s(committed),
            "uncalled": s(committed - paid_in),
            "invested_at_cost": s(invested_cost),
            "positions_at_cost": positions_at_cost,
        },
        # ties out by construction; surfaced so the UI can show a check
        "balances": q(net_assets) == q(ending_capital),
    }


# --- follow-on investment rounds (Rundit-style per-round history) --------------
def _round_view(r: InvestmentRound) -> dict:
    return {
        "id": r.id,
        "round_label": r.round_label,
        "instrument": r.instrument,
        "amount": str(q(r.amount)),
        "invested_on": r.invested_on,
        "note": r.note,
    }


def add_investment_round(
    db: Session, investment: PortfolioInvestment, data: dict, user_id: str
) -> dict:
    """Record a follow-on cheque: the round is appended to the history and the
    company's total cost (PortfolioInvestment.amount) grows by the amount, so
    SOI / NAV / financials stay consistent."""
    amount = Decimal(str(data["amount"]))
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "amount must be positive")
    r = InvestmentRound(
        investment_id=investment.id,
        fund_id=investment.fund_id,
        round_label=data.get("round_label"),
        instrument=data.get("instrument") or "equity",
        amount=amount,
        invested_on=data.get("invested_on"),
        note=data.get("note"),
        created_by=user_id,
    )
    investment.amount = Decimal(investment.amount) + amount
    db.add(r)
    db.commit()
    db.refresh(r)
    return _round_view(r)


def investment_rounds(db: Session, investment: PortfolioInvestment) -> dict:
    rounds = (
        db.query(InvestmentRound)
        .filter_by(investment_id=investment.id)
        .order_by(InvestmentRound.invested_on, InvestmentRound.created_at)
        .all()
    )
    followons = sum((Decimal(r.amount) for r in rounds), Decimal("0"))
    return {
        "initial": {
            "amount": str(q(Decimal(investment.amount) - followons)),
            "instrument": investment.instrument,
            "invested_on": investment.invested_on,
        },
        "rounds": [_round_view(r) for r in rounds],
        "total_cost": str(q(investment.amount)),
    }


# --- fund expense ledger --------------------------------------------------------
EXPENSE_CATEGORIES = ("legal", "audit", "administration", "diligence", "other")


def _expense_view(e: FundExpense) -> dict:
    return {
        "id": e.id,
        "date": e.date,
        "category": e.category,
        "amount": str(q(e.amount)),
        "note": e.note,
    }


def add_fund_expense(db: Session, fund: Fund, data: dict, user_id: str) -> dict:
    amount = Decimal(str(data["amount"]))
    if amount <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "amount must be positive")
    e = FundExpense(
        fund_id=fund.id,
        date=data["date"],
        category=data.get("category") or "other",
        amount=amount,
        note=data.get("note"),
        created_by=user_id,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _expense_view(e)


def list_fund_expenses(db: Session, fund: Fund) -> dict:
    rows = (
        db.query(FundExpense)
        .filter_by(fund_id=fund.id)
        .order_by(FundExpense.date.desc(), FundExpense.created_at.desc())
        .all()
    )
    return {
        "expenses": [_expense_view(e) for e in rows],
        "total": str(q(sum((Decimal(e.amount) for e in rows), Decimal("0")))),
        "categories": EXPENSE_CATEGORIES,
    }


def delete_fund_expense(db: Session, fund: Fund, expense_id: str) -> None:
    e = db.get(FundExpense, expense_id)
    if e is None or e.fund_id != fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    db.delete(e)
    db.commit()

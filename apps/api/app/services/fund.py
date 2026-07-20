"""Fund administration service (HLD §J). Capital accounts are a projection
over the drawdown and distribution ledgers (ADR-2): drawn = sum of paid
drawdown notices; distributed = sum of LP distributions.

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

from ..clock import now_ist, today_ist
from ..models.fund import (
    CapitalCall,
    Distribution,
    DistributionKind,
    DrawdownNotice,
    FeeCharge,
    Fund,
    FundPlan,
    LP,
    LPDistribution,
    PortfolioInvestment,
    PortfolioKPI,
)
from .fund_perf import management_fee_by_lp, units_for

from .money import q  # shared paise quantisation


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


def mark_paid(db: Session, notice: DrawdownNotice) -> DrawdownNotice:
    if not notice.paid:
        notice.paid = True
        # IST, same frame as today_ist(): pref accrual compares this date
        # against distribution dates — a mixed-timezone date can be a day off
        notice.paid_at = now_ist()
        db.commit()
        db.refresh(notice)
    return notice


def _paid_in_by_lp(db: Session, fund_id: str) -> dict[str, Decimal]:
    rows = db.query(DrawdownNotice).filter_by(fund_id=fund_id, paid=True).all()
    out: dict[str, Decimal] = {}
    for r in rows:
        out[r.lp_id] = out.get(r.lp_id, Decimal("0")) + Decimal(r.amount)
    return out


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


def _fees_charged_by_lp(db: Session, fund_id: str) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for f in db.query(FeeCharge).filter_by(fund_id=fund_id):
        out[f.lp_id] = out.get(f.lp_id, Decimal("0")) + Decimal(f.amount)
    return out


def charge_fees(db: Session, fund: Fund, as_of: datetime.date) -> dict:
    """Crystallise the management fee: charge each LP the fee accrued to
    `as_of` minus what has already been charged. Append-only and therefore
    safe to run repeatedly (a second run the same day charges nothing)."""
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


def _moic(value: Decimal, cost: Decimal) -> str | None:
    return str((value / cost).quantize(Decimal("0.01"), ROUND_HALF_UP)) if cost > 0 else None


def schedule_of_investments(db: Session, fund: Fund) -> dict:
    """The fund's Schedule of Investments (FR-J-11): per holding — cost, current
    mark (fair value, else held at cost), ownership %, MOIC, unrealised gain and
    share of NAV — with portfolio totals. GP-facing; the basis for LP
    look-through reporting below."""
    invs = db.query(PortfolioInvestment).filter_by(fund_id=fund.id).all()
    holdings = []
    tot_cost = tot_value = Decimal("0")
    for p in invs:
        cost = Decimal(p.amount)
        marked = p.current_value is not None
        value = Decimal(p.current_value) if marked else cost
        tot_cost += cost
        tot_value += value
        holdings.append(
            {
                "id": p.id,
                "company_name": p.company_name,
                "instrument": p.instrument,
                "invested_on": p.invested_on.isoformat() if p.invested_on else None,
                "cost": str(q(cost)),
                "current_value": str(q(value)),
                "marked": marked,
                "ownership_pct": str(p.ownership_pct),
                "moic": _moic(value, cost),
                "unrealized_gain": str(q(value - cost)),
            }
        )
    # share of NAV once the total is known
    for h in holdings:
        h["pct_of_nav"] = (
            round(Decimal(h["current_value"]) / tot_value * 100, 2) if tot_value > 0 else 0.0
        )
    holdings.sort(key=lambda h: Decimal(h["current_value"]), reverse=True)
    return {
        "fund_id": fund.id,
        "holdings": holdings,
        "totals": {
            "cost": str(q(tot_cost)),
            "current_value": str(q(tot_value)),
            "unrealized_gain": str(q(tot_value - tot_cost)),
            "moic": _moic(tot_value, tot_cost),
            "count": len(holdings),
        },
    }


def lp_share(db: Session, fund: Fund, lp: LP) -> Decimal:
    """An LP's economic share of the fund (0..1): paid-in capital as a fraction
    of total paid-in, falling back to commitment share before any drawdown."""
    paid_in = _paid_in_by_lp(db, fund.id)
    total = sum(paid_in.values(), Decimal("0"))
    if total > 0:
        return paid_in.get(lp.id, Decimal("0")) / total
    commitments = {x.id: Decimal(x.commitment) for x in db.query(LP).filter_by(fund_id=fund.id)}
    ctotal = sum(commitments.values(), Decimal("0"))
    return commitments.get(lp.id, Decimal("0")) / ctotal if ctotal > 0 else Decimal("0")


def lp_look_through(db: Session, fund: Fund, lp: LP) -> dict:
    """LP look-through (FR-K, FR-J-11): the LP's pro-rata slice of each of the
    fund's underlying holdings — see *through* the fund position to the
    companies it exposes them to. Uses the fund's own reported marks, so no
    portfolio-company privacy boundary is crossed."""
    soi = schedule_of_investments(db, fund)
    share = lp_share(db, fund, lp)
    holdings = [
        {
            "company_name": h["company_name"],
            "instrument": h["instrument"],
            "fund_cost": h["cost"],
            "fund_value": h["current_value"],
            "look_through_cost": str(q(Decimal(h["cost"]) * share)),
            "look_through_value": str(q(Decimal(h["current_value"]) * share)),
            "moic": h["moic"],
        }
        for h in soi["holdings"]
    ]
    return {
        "fund_id": fund.id,
        "share_pct": round(share * 100, 4),
        "holdings": holdings,
        "totals": {
            "look_through_cost": str(q(Decimal(soi["totals"]["cost"]) * share)),
            "look_through_value": str(q(Decimal(soi["totals"]["current_value"]) * share)),
        },
    }


def capital_accounts(db: Session, fund: Fund) -> dict:
    lps = db.query(LP).filter_by(fund_id=fund.id).all()
    paid_in = _paid_in_by_lp(db, fund.id)
    fees = _fees_charged_by_lp(db, fund.id)
    dist_rows = db.query(LPDistribution).filter_by(fund_id=fund.id).all()
    distributed: dict[str, Decimal] = {}
    for r in dist_rows:
        distributed[r.lp_id] = distributed.get(r.lp_id, Decimal("0")) + Decimal(r.amount)

    accounts = []
    tot_committed = tot_drawn = tot_distributed = tot_fees = Decimal("0")
    for lp in lps:
        committed = Decimal(lp.commitment)
        drawn = paid_in.get(lp.id, Decimal("0"))
        dist = distributed.get(lp.id, Decimal("0"))
        fee = fees.get(lp.id, Decimal("0"))
        tot_committed += committed
        tot_drawn += drawn
        tot_distributed += dist
        tot_fees += fee
        accounts.append(
            {
                "lp_id": lp.id,
                "lp_name": lp.name,
                "committed": str(q(committed)),
                "drawn": str(q(drawn)),
                "remaining": str(q(committed - drawn)),
                "distributed": str(q(dist)),
                "fees_charged": str(q(fee)),
                "units": str(units_for(drawn)),
            }
        )
    return {
        "fund_id": fund.id,
        "totals": {
            "committed": str(q(tot_committed)),
            "drawn": str(q(tot_drawn)),
            "remaining": str(q(tot_committed - tot_drawn)),
            "distributed": str(q(tot_distributed)),
            "fees_charged": str(q(tot_fees)),
        },
        "accounts": accounts,
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
    }


# --- portfolio-company monitoring (Carta "portfolio monitoring") -------------
LOW_RUNWAY_MONTHS = 6  # flag threshold


def _runway_months(cash: Decimal | None, burn: Decimal | None) -> float | None:
    if cash is None or burn is None or burn <= 0:
        return None
    return round(float(cash / burn), 1)


def add_kpi(db: Session, investment: PortfolioInvestment, data: dict) -> PortfolioKPI:
    kpi = PortfolioKPI(investment_id=investment.id, fund_id=investment.fund_id, **data)
    db.add(kpi)
    db.commit()
    db.refresh(kpi)
    return kpi


def _kpi_view(k: PortfolioKPI) -> dict:
    return {
        "id": k.id,
        "period_label": k.period_label,
        "as_of": k.as_of,
        "revenue": str(q(k.revenue)) if k.revenue is not None else None,
        "cash": str(q(k.cash)) if k.cash is not None else None,
        "monthly_burn": str(q(k.monthly_burn)) if k.monthly_burn is not None else None,
        "headcount": k.headcount,
        "runway_months": _runway_months(k.cash, k.monthly_burn),
        "note": k.note,
    }


def kpi_history(db: Session, investment: PortfolioInvestment) -> list[dict]:
    rows = (
        db.query(PortfolioKPI)
        .filter_by(investment_id=investment.id)
        .order_by(PortfolioKPI.as_of)
        .all()
    )
    return [_kpi_view(k) for k in rows]


def portfolio_monitoring(db: Session, fund: Fund) -> dict:
    """Latest reported KPIs per portfolio company + period-over-period revenue
    growth, runway and low-runway flag, with portfolio-level roll-ups."""
    companies = []
    tot_revenue = Decimal("0")
    tot_cash = Decimal("0")
    low_runway = 0
    reporting = 0

    for inv in db.query(PortfolioInvestment).filter_by(fund_id=fund.id):
        rows = (
            db.query(PortfolioKPI)
            .filter_by(investment_id=inv.id)
            .order_by(PortfolioKPI.as_of.desc())
            .all()
        )
        latest = rows[0] if rows else None
        prev = rows[1] if len(rows) > 1 else None

        growth = None
        if latest and prev and latest.revenue is not None and prev.revenue and Decimal(prev.revenue) != 0:
            growth = round(
                float((Decimal(latest.revenue) - Decimal(prev.revenue)) / Decimal(prev.revenue) * 100), 1
            )
        runway = _runway_months(latest.cash, latest.monthly_burn) if latest else None

        if latest:
            reporting += 1
            if latest.revenue is not None:
                tot_revenue += Decimal(latest.revenue)
            if latest.cash is not None:
                tot_cash += Decimal(latest.cash)
            if runway is not None and runway < LOW_RUNWAY_MONTHS:
                low_runway += 1

        companies.append({
            "investment_id": inv.id,
            "company_name": inv.company_name,
            "ownership_pct": str(inv.ownership_pct),
            "periods": len(rows),
            "latest": _kpi_view(latest) if latest else None,
            "revenue_growth_pct": growth,
            "runway_months": runway,
            "low_runway": runway is not None and runway < LOW_RUNWAY_MONTHS,
            "revenue_series": [
                {"x": k.as_of.isoformat(), "y": float(k.revenue)}
                for k in sorted(rows, key=lambda r: r.as_of)
                if k.revenue is not None
            ],
        })

    return {
        "fund_id": fund.id,
        "totals": {
            "companies": db.query(PortfolioInvestment).filter_by(fund_id=fund.id).count(),
            "reporting": reporting,
            "latest_revenue": str(q(tot_revenue)),
            "cash": str(q(tot_cash)),
            "low_runway": low_runway,
        },
        "companies": companies,
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

    net_operations = unrealized - fees            # = statement-of-operations bottom line
    cash = paid_in - invested_cost - distributed_lps - carry - fees
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
            "net_increase_from_operations": s(net_operations),
        },
        "cash_flow": {
            "contributions": s(paid_in),
            "investments_made": s(-invested_cost),
            "distributions_to_lps": s(-distributed_lps),
            "carry_paid": s(-carry),
            "management_fees_paid": s(-fees),
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

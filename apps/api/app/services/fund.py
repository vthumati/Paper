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
from statistics import median

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
    KPIDefinition,
    KPIRequest,
    KPIRequestStatus,
    LP,
    LPDistribution,
    LPProspect,
    LPProspectStage,
    MetricAlertRule,
    PortfolioInvestment,
    PortfolioKPI,
    PortfolioValuation,
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


def period_activity(
    db: Session, fund: Fund, start: datetime.date, end: datetime.date
) -> dict:
    """Capital calls and distributions falling in a reporting period (FR-J-22
    quarterly LP report): calls by due date, distributions by their date, each
    falling back to creation date when undated."""
    calls = []
    called = Decimal("0")
    for c in db.query(CapitalCall).filter_by(fund_id=fund.id).order_by(CapitalCall.call_no):
        on = c.due_date or c.created_at.date()
        if not (start <= on <= end):
            continue
        amount = sum(
            (Decimal(n.amount) for n in db.query(DrawdownNotice).filter_by(call_id=c.id)),
            Decimal("0"),
        )
        called += amount
        calls.append(
            {
                "call_no": c.call_no,
                "date": on.isoformat(),
                "purpose": c.purpose,
                "amount": str(q(amount)),
            }
        )

    dists = []
    distributed = Decimal("0")
    for d in db.query(Distribution).filter_by(fund_id=fund.id).order_by(Distribution.dist_no):
        on = d.date or d.created_at.date()
        if not (start <= on <= end):
            continue
        distributed += Decimal(d.gross_amount)
        dists.append(
            {
                "dist_no": d.dist_no,
                "date": on.isoformat(),
                "kind": d.kind.value,
                "gross_amount": str(q(Decimal(d.gross_amount))),
                "carry_amount": str(q(Decimal(d.carry_amount))),
            }
        )
    return {
        "capital_calls": calls,
        "distributions": dists,
        "totals": {"called": str(q(called)), "distributed": str(q(distributed))},
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
    # custom metric values are kept only for keys the fund has defined (FR-J-23)
    custom = data.pop("custom", None)
    if custom:
        defined = {
            d.key for d in db.query(KPIDefinition).filter_by(fund_id=investment.fund_id)
        }
        custom = {
            k: str(Decimal(str(v)))
            for k, v in custom.items()
            if k in defined and v is not None
        }
    kpi = PortfolioKPI(
        investment_id=investment.id,
        fund_id=investment.fund_id,
        custom=custom or None,
        **data,
    )
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
        "custom": k.custom or {},
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
            "contact_email": inv.contact_email,
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


# --- custom KPI definitions + ESG presets (FR-J-23) ---------------------------
KPI_UNITS = ("inr", "number", "pct")

ESG_KPI_PRESETS = [
    {"key": "female_headcount_pct", "label": "Female headcount %", "unit": "pct"},
    {"key": "independent_directors_pct", "label": "Independent directors %", "unit": "pct"},
    {"key": "ghg_emissions_tco2e", "label": "GHG emissions (tCO2e)", "unit": "number"},
    {"key": "energy_use_kwh", "label": "Energy use (kWh)", "unit": "number"},
    {"key": "csr_spend", "label": "CSR spend", "unit": "inr"},
]


def _kpi_key(label: str) -> str:
    out: list[str] = []
    for ch in label.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "_":
            out.append("_")
    return "".join(out).strip("_")[:64]


def _definition_view(d: KPIDefinition) -> dict:
    return {"id": d.id, "key": d.key, "label": d.label, "unit": d.unit}


def list_kpi_definitions(db: Session, fund: Fund) -> list[dict]:
    rows = (
        db.query(KPIDefinition)
        .filter_by(fund_id=fund.id)
        .order_by(KPIDefinition.created_at)
        .all()
    )
    return [_definition_view(d) for d in rows]


def create_kpi_definition(
    db: Session, fund: Fund, data: dict, user_id: str
) -> KPIDefinition:
    unit = data.get("unit") or "number"
    if unit not in KPI_UNITS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unit must be one of {KPI_UNITS}")
    key = _kpi_key(data.get("key") or data["label"])
    if not key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "label must contain letters or digits")
    if db.query(KPIDefinition).filter_by(fund_id=fund.id, key=key).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"metric '{key}' is already defined")
    d = KPIDefinition(
        fund_id=fund.id, key=key, label=data["label"].strip(), unit=unit, created_by=user_id
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def delete_kpi_definition(db: Session, fund: Fund, definition_id: str) -> None:
    d = db.get(KPIDefinition, definition_id)
    if d is None or d.fund_id != fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Metric definition not found")
    # historical values stay in PortfolioKPI.custom; they just stop being shown
    db.delete(d)
    db.commit()


# --- internal benchmarking: portfolio medians (FR-J-24) -----------------------
CORE_METRICS = [
    {"key": "revenue", "label": "Revenue", "unit": "inr"},
    {"key": "revenue_growth_pct", "label": "Revenue growth %", "unit": "pct"},
    {"key": "monthly_burn", "label": "Monthly burn", "unit": "inr"},
    {"key": "runway_months", "label": "Runway (months)", "unit": "number"},
    {"key": "headcount", "label": "Headcount", "unit": "number"},
]


def metric_options(db: Session, fund: Fund) -> list[dict]:
    """The comparable metric catalog: core KPIs + the fund's custom
    definitions (keyed `custom.<key>`). Shared by benchmarks and alerts."""
    return CORE_METRICS + [
        {"key": f"custom.{d['key']}", "label": d["label"], "unit": d["unit"]}
        for d in list_kpi_definitions(db, fund)
    ]


def portfolio_benchmarks(db: Session, fund: Fund) -> dict:
    """Companies side-by-side on the core and custom metrics from each one's
    latest reported period, against the portfolio median. Pure derivation."""
    defs = list_kpi_definitions(db, fund)
    metrics = metric_options(db, fund)

    rows = []
    for c in portfolio_monitoring(db, fund)["companies"]:
        latest = c["latest"] or {}
        values: dict[str, float | None] = {
            "revenue": float(latest["revenue"]) if latest.get("revenue") else None,
            "revenue_growth_pct": c["revenue_growth_pct"],
            "monthly_burn": float(latest["monthly_burn"]) if latest.get("monthly_burn") else None,
            "runway_months": c["runway_months"],
            "headcount": latest.get("headcount"),
        }
        for d in defs:
            v = (latest.get("custom") or {}).get(d["key"])
            values[f"custom.{d['key']}"] = float(v) if v is not None else None
        rows.append(
            {
                "investment_id": c["investment_id"],
                "company_name": c["company_name"],
                "values": values,
            }
        )

    medians = {}
    for m in metrics:
        xs = [r["values"][m["key"]] for r in rows if r["values"][m["key"]] is not None]
        medians[m["key"]] = round(median(xs), 2) if xs else None
    return {"fund_id": fund.id, "metrics": metrics, "rows": rows, "medians": medians}


# --- metric alert rules (Visible-style thresholds) -----------------------------
ALERT_COMPARATORS = ("lt", "gt")
ALERT_SEVERITIES = ("high", "warn")


def _rule_view(r: MetricAlertRule) -> dict:
    return {
        "id": r.id,
        "metric": r.metric,
        "comparator": r.comparator,
        "threshold": str(r.threshold),
        "severity": r.severity,
    }


def list_alert_rules(db: Session, fund: Fund) -> dict:
    rows = (
        db.query(MetricAlertRule)
        .filter_by(fund_id=fund.id)
        .order_by(MetricAlertRule.created_at)
        .all()
    )
    return {"rules": [_rule_view(r) for r in rows], "metrics": metric_options(db, fund)}


def create_alert_rule(db: Session, fund: Fund, data: dict, user_id: str) -> dict:
    if data["comparator"] not in ALERT_COMPARATORS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"comparator must be one of {ALERT_COMPARATORS}")
    if data.get("severity", "warn") not in ALERT_SEVERITIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"severity must be one of {ALERT_SEVERITIES}")
    known = {m["key"] for m in metric_options(db, fund)}
    if data["metric"] not in known:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown metric '{data['metric']}'")
    r = MetricAlertRule(
        fund_id=fund.id,
        metric=data["metric"],
        comparator=data["comparator"],
        threshold=Decimal(str(data["threshold"])),
        severity=data.get("severity", "warn"),
        created_by=user_id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _rule_view(r)


def delete_alert_rule(db: Session, fund: Fund, rule_id: str) -> None:
    r = db.get(MetricAlertRule, rule_id)
    if r is None or r.fund_id != fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert rule not found")
    db.delete(r)
    db.commit()


def _fmt_metric(value: float | Decimal, unit: str) -> str:
    if unit == "inr":
        return _inr(value)
    if unit == "pct":
        return f"{round(float(value), 1)}%"
    return f"{round(float(value), 1):g}"


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


# --- SEBI independent portfolio valuation (FR-J-15) --------------------------
VALUATION_METHODOLOGIES = {
    "ipev_market": "IPEV — market multiples",
    "ipev_recent_txn": "IPEV — recent transaction price",
    "dcf": "Discounted cash flow",
    "nav": "Net assets / book value",
    "cost": "Cost (no observable change)",
}


def set_valuation_policy(db: Session, fund: Fund, valuer_name, frequency_months) -> Fund:
    fund.valuer_name = valuer_name
    fund.valuation_frequency_months = frequency_months
    db.commit()
    db.refresh(fund)
    return fund


def record_valuation(db: Session, investment: PortfolioInvestment, data: dict) -> PortfolioValuation:
    """Append a valuation and roll it into the holding's mark (latest by as_of)."""
    val = PortfolioValuation(investment_id=investment.id, fund_id=investment.fund_id, **data)
    db.add(val)
    db.flush()
    # keep the holding's mark = latest valuation by as_of
    latest = (
        db.query(PortfolioValuation)
        .filter_by(investment_id=investment.id)
        .order_by(PortfolioValuation.as_of.desc(), PortfolioValuation.created_at.desc())
        .first()
    )
    investment.current_value = latest.value
    investment.marked_on = latest.as_of
    db.commit()
    db.refresh(val)
    return val


def _valuation_view(v: PortfolioValuation) -> dict:
    return {
        "id": v.id,
        "as_of": v.as_of,
        "value": str(q(v.value)),
        "methodology": v.methodology,
        "methodology_label": VALUATION_METHODOLOGIES.get(v.methodology, v.methodology),
        "valuer": v.valuer,
        "is_independent": v.is_independent,
        "note": v.note,
    }


def valuation_history(db: Session, investment: PortfolioInvestment) -> list[dict]:
    rows = (
        db.query(PortfolioValuation)
        .filter_by(investment_id=investment.id)
        .order_by(PortfolioValuation.as_of.desc())
        .all()
    )
    return [_valuation_view(v) for v in rows]


def valuation_summary(db: Session, fund: Fund) -> dict:
    """Per-holding latest valuation + staleness vs the fund's valuation policy,
    with SEBI-oriented roll-ups (valued / stale / independent counts)."""
    freq = fund.valuation_frequency_months or 12
    today = today_ist()
    stale_before = today - datetime.timedelta(days=int(freq * 30.4))

    holdings = []
    valued = stale = independent = 0
    for inv in db.query(PortfolioInvestment).filter_by(fund_id=fund.id):
        latest = (
            db.query(PortfolioValuation)
            .filter_by(investment_id=inv.id)
            .order_by(PortfolioValuation.as_of.desc(), PortfolioValuation.created_at.desc())
            .first()
        )
        count = db.query(PortfolioValuation).filter_by(investment_id=inv.id).count()
        is_stale = latest is None or latest.as_of < stale_before
        if latest is not None:
            valued += 1
            if latest.is_independent:
                independent += 1
        if is_stale:
            stale += 1
        holdings.append({
            "investment_id": inv.id,
            "company_name": inv.company_name,
            "cost": str(q(inv.amount)),
            "valuations": count,
            "latest": _valuation_view(latest) if latest else None,
            "stale": is_stale,
        })

    return {
        "fund_id": fund.id,
        "policy": {
            "valuer_name": fund.valuer_name,
            "frequency_months": freq,
        },
        "methodologies": VALUATION_METHODOLOGIES,
        "totals": {
            "holdings": len(holdings),
            "valued": valued,
            "stale": stale,
            "independent": independent,
        },
        "holdings": holdings,
    }


# --- LP-fundraising CRM (raising the fund from prospective LPs) ---------------
# pipeline stages that count as "still being worked" (not yet won or lost)
_ACTIVE_PROSPECT_STAGES = {
    LPProspectStage.PROSPECT,
    LPProspectStage.CONTACTED,
    LPProspectStage.MEETING,
    LPProspectStage.DILIGENCE,
    LPProspectStage.SOFT_CIRCLED,
}


def add_prospect(db: Session, fund: Fund, data: dict) -> LPProspect:
    p = LPProspect(fund_id=fund.id, **data)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def set_prospect_stage(db: Session, prospect: LPProspect, stage: LPProspectStage) -> LPProspect:
    prospect.stage = stage
    db.commit()
    db.refresh(prospect)
    return prospect


def convert_prospect_to_lp(db: Session, prospect: LPProspect, commitment: Decimal | None) -> LP:
    """Turn a won prospect into an LP with a commitment. Idempotent-guarded:
    a prospect already linked to an LP can't be converted twice."""
    if prospect.lp_id:
        raise HTTPException(status.HTTP_409_CONFLICT, "Prospect already converted to an LP")
    amount = commitment if commitment is not None else Decimal(prospect.target_commitment)
    lp = LP(fund_id=prospect.fund_id, name=prospect.name, email=prospect.email, commitment=amount)
    db.add(lp)
    db.flush()
    prospect.lp_id = lp.id
    prospect.stage = LPProspectStage.COMMITTED
    db.commit()
    db.refresh(lp)
    return lp


def _prospect_view(p: LPProspect) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "firm": p.firm,
        "kind": p.kind,
        "email": p.email,
        "stage": p.stage.value,
        "target_commitment": str(q(p.target_commitment)),
        "notes": p.notes,
        "lp_id": p.lp_id,
        "next_followup_on": p.next_followup_on,
    }


def fundraise_summary(db: Session, fund: Fund) -> dict:
    """The fund's own raise: prospect pipeline by stage + progress toward the
    target corpus. 'Committed' is the actual committed LP capital; 'soft-circled'
    and 'pipeline' come from the prospect targets."""
    prospects = db.query(LPProspect).filter_by(fund_id=fund.id).all()
    committed = sum(
        (Decimal(lp.commitment) for lp in db.query(LP).filter_by(fund_id=fund.id)), Decimal("0")
    )
    target = Decimal(fund.target_corpus or 0)

    by_stage: dict[str, dict] = {}
    soft_circled = Decimal("0")
    pipeline = Decimal("0")
    for p in prospects:
        row = by_stage.setdefault(p.stage.value, {"count": 0, "target": Decimal("0")})
        row["count"] += 1
        row["target"] += Decimal(p.target_commitment)
        if p.stage == LPProspectStage.SOFT_CIRCLED:
            soft_circled += Decimal(p.target_commitment)
        if p.stage in _ACTIVE_PROSPECT_STAGES:
            pipeline += Decimal(p.target_commitment)

    return {
        "fund_id": fund.id,
        "target_corpus": str(q(target)),
        "committed": str(q(committed)),
        "soft_circled": str(q(soft_circled)),
        "pipeline": str(q(pipeline)),
        "progress_pct": round(float(committed / target * 100), 1) if target > 0 else None,
        "by_stage": {k: {"count": v["count"], "target": str(q(v["target"]))} for k, v in by_stage.items()},
        "prospects": [_prospect_view(p) for p in prospects],
    }


# --- KPI reporting requests (investee self-service, Vestberry-style) ----------
def create_kpi_request(
    db: Session, investment: PortfolioInvestment, data: dict, user_id: str
) -> KPIRequest:
    """Ask the company's reporting contact for one period of KPIs. Keeps the
    investment's contact_email in sync and notifies the contact if they have a
    Paper account (the request also appears in their portal either way)."""
    from ..models.identity import User
    from .notification import notify

    investment.contact_email = data["contact_email"]
    req = KPIRequest(
        investment_id=investment.id,
        fund_id=investment.fund_id,
        created_by=user_id,
        **data,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    contact = db.query(User).filter_by(email=req.contact_email).first()
    if contact:
        notify(
            db,
            contact.id,
            "kpi_request",
            f"KPI request: {investment.company_name} — {req.period_label}",
            f"Report revenue, cash, burn and headcount{f' by {req.due_date}' if req.due_date else ''} from your portal.",
        )
    return req


def _kpi_request_view(r: KPIRequest, company_name: str | None = None) -> dict:
    return {
        "id": r.id,
        "investment_id": r.investment_id,
        "company_name": company_name,
        "period_label": r.period_label,
        "as_of": r.as_of,
        "due_date": r.due_date,
        "contact_email": r.contact_email,
        "status": r.status.value,
        "overdue": bool(
            r.status == KPIRequestStatus.PENDING and r.due_date and r.due_date < today_ist()
        ),
        "revenue": str(q(r.revenue)) if r.revenue is not None else None,
        "cash": str(q(r.cash)) if r.cash is not None else None,
        "monthly_burn": str(q(r.monthly_burn)) if r.monthly_burn is not None else None,
        "headcount": r.headcount,
        "note": r.note,
        "submitted_at": r.submitted_at,
        "kpi_id": r.kpi_id,
    }


def list_kpi_requests(db: Session, fund: Fund) -> list[dict]:
    names = {
        i.id: i.company_name
        for i in db.query(PortfolioInvestment).filter_by(fund_id=fund.id)
    }
    return [
        _kpi_request_view(r, names.get(r.investment_id))
        for r in db.query(KPIRequest)
        .filter_by(fund_id=fund.id)
        .order_by(KPIRequest.created_at.desc())
    ]


def accept_kpi_request(db: Session, req: KPIRequest) -> PortfolioKPI:
    """GP accepts a submitted request — the values become a PortfolioKPI period."""
    if req.status != KPIRequestStatus.SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Request has not been submitted")
    inv = db.get(PortfolioInvestment, req.investment_id)
    kpi = add_kpi(
        db,
        inv,
        {
            "period_label": req.period_label,
            "as_of": req.as_of,
            "revenue": req.revenue,
            "cash": req.cash,
            "monthly_burn": req.monthly_burn,
            "headcount": req.headcount,
            "note": req.note,
        },
    )
    req.kpi_id = kpi.id
    req.status = KPIRequestStatus.ACCEPTED
    db.commit()
    return kpi


def reopen_kpi_request(db: Session, req: KPIRequest) -> KPIRequest:
    """Send a submitted request back for resubmission (values look wrong)."""
    if req.status != KPIRequestStatus.SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a submitted request can be reopened")
    req.status = KPIRequestStatus.PENDING
    req.submitted_at = None
    db.commit()
    db.refresh(req)
    return req


# --- portfolio signals (Vestberry-style risk early-warning) -------------------
REVENUE_DECLINE_HIGH_PCT = 20   # QoQ drop beyond this is high severity
SILENT_REPORTING_DAYS = 183     # ~6 months without a reported period
FOLLOW_ON_RUNWAY_MONTHS = 12    # healthy runway threshold for follow-on


def _inr(value) -> str:
    """₹ with Indian lakh/crore digit grouping (12,34,56,789) for signal text."""
    n = int(Decimal(value))
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return f"₹{sign}{s}"


def portfolio_signals(db: Session, fund: Fund) -> dict:
    """Rules-based signals over the KPI history and marks — which companies
    need attention (declining revenue, short runway, impaired marks, gone
    silent) and which look ready for follow-on capital. Pure derivation."""
    today = today_ist()
    companies = []
    totals = {"high": 0, "warn": 0, "info": 0, "positive": 0}
    alert_rules = db.query(MetricAlertRule).filter_by(fund_id=fund.id).all()
    metric_meta = {m["key"]: m for m in metric_options(db, fund)} if alert_rules else {}

    for inv in db.query(PortfolioInvestment).filter_by(fund_id=fund.id):
        rows = (
            db.query(PortfolioKPI)
            .filter_by(investment_id=inv.id)
            .order_by(PortfolioKPI.as_of.desc())
            .all()
        )
        latest = rows[0] if rows else None
        prev = rows[1] if len(rows) > 1 else None
        signals: list[dict] = []

        def add(kind: str, severity: str, message: str) -> None:
            signals.append({"kind": kind, "severity": severity, "message": message})
            totals[severity] += 1

        # revenue decline, period over period
        growth = None
        if latest and prev and latest.revenue is not None and prev.revenue:
            change = Decimal(latest.revenue) - Decimal(prev.revenue)
            growth = float(change / Decimal(prev.revenue) * 100)
            if change < 0:
                drop = abs(round(growth, 1))
                add(
                    "revenue_decline",
                    "high" if drop > REVENUE_DECLINE_HIGH_PCT else "warn",
                    f"Revenue down {drop}% vs {prev.period_label} "
                    f"({_inr(prev.revenue)} → {_inr(latest.revenue)})",
                )

        # runway from the latest period
        runway = _runway_months(latest.cash, latest.monthly_burn) if latest else None
        if runway is not None and runway < LOW_RUNWAY_MONTHS:
            add("low_runway", "high", f"Runway {runway} months — under {LOW_RUNWAY_MONTHS}")

        # mark below cost (impairment)
        if inv.current_value is not None and Decimal(inv.current_value) < Decimal(inv.amount):
            pct = round(
                float((Decimal(inv.amount) - Decimal(inv.current_value)) / Decimal(inv.amount) * 100), 1
            )
            add(
                "mark_below_cost",
                "warn",
                f"Marked {pct}% below cost ({_inr(inv.amount)} → {_inr(inv.current_value)})",
            )

        # reporting cadence
        if latest is None:
            add("never_reported", "info", "No KPI periods reported yet — request KPIs")
        elif (today - latest.as_of).days > SILENT_REPORTING_DAYS:
            add(
                "reporting_silent",
                "warn",
                f"No report since {latest.period_label} ({latest.as_of}) — over 6 months",
            )

        # fund-defined metric alerts against the latest period
        if alert_rules:
            values: dict[str, float | None] = {
                "revenue": float(latest.revenue) if latest and latest.revenue is not None else None,
                "revenue_growth_pct": growth,
                "monthly_burn": float(latest.monthly_burn) if latest and latest.monthly_burn is not None else None,
                "runway_months": runway,
                "headcount": latest.headcount if latest else None,
            }
            for k, v in ((latest.custom or {}).items() if latest else ()):
                if v is not None:
                    values[f"custom.{k}"] = float(v)
            for r in alert_rules:
                v = values.get(r.metric)
                meta = metric_meta.get(r.metric)
                if v is None or meta is None:
                    continue
                threshold = float(r.threshold)
                if (r.comparator == "lt" and v < threshold) or (r.comparator == "gt" and v > threshold):
                    word = "below" if r.comparator == "lt" else "above"
                    add(
                        "metric_alert",
                        r.severity,
                        f"{meta['label']} {_fmt_metric(v, meta['unit'])} — {word} the "
                        f"{_fmt_metric(threshold, meta['unit'])} alert threshold",
                    )

        # the positive signal: growing and well-funded
        if (
            growth is not None
            and growth > 0
            and runway is not None
            and runway >= FOLLOW_ON_RUNWAY_MONTHS
        ):
            add(
                "follow_on_candidate",
                "positive",
                f"Growing {round(growth, 1)}% with {runway} months runway — follow-on candidate",
            )

        if signals:
            companies.append({
                "investment_id": inv.id,
                "company_name": inv.company_name,
                "signals": signals,
            })

    total_companies = db.query(PortfolioInvestment).filter_by(fund_id=fund.id).count()
    return {
        "fund_id": fund.id,
        "totals": {**totals, "clear": total_companies - len(companies)},
        "companies": companies,
    }

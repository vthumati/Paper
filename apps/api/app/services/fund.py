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
    LP,
    LPDistribution,
    PortfolioInvestment,
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

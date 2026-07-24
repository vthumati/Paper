"""LP capital & portal views: capital accounts, period activity, schedule of
investments and LP look-through. Capital accounts are a projection over the
drawdown and distribution ledgers (ADR-2)."""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ...models.fund import (
    CapitalCall,
    Distribution,
    DrawdownNotice,
    Fund,
    LP,
    LPDistribution,
    PortfolioInvestment,
)
from ..fund_perf import units_for
from ..money import q  # shared paise quantisation
from ._common import _fees_charged_by_lp, _paid_in_by_lp


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

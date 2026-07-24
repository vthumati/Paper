"""Round scenario modeling (FR-C-4): the pro-forma cap table for a
HYPOTHETICAL round — nothing is written to the ledger.

Conventions (the market-standard ones):
 - the pre-money is divided by the pre-round fully-diluted share count
   (issued + unexercised options + unallocated pool) to get the price;
   alternatively the caller supplies the price directly.
 - a pool top-up can be timed either side of the round (the "option pool
   shuffle"): "pre" puts it in the pre-money FD, so it comes out of existing
   holders and the new investor's stake is protected; "post" creates it after
   the round, so it dilutes everyone — new investors included.
 - outstanding SAFEs/notes convert at the round (discount/cap terms applied
   at the scenario price) alongside the new money.
"""
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models.captable import SecurityClass
from .diluted import POOL_ROW, anti_dilution_preview, fully_diluted

CENTS = Decimal("0.01")
PRICE4 = Decimal("0.0001")


def model_round(
    db: Session,
    entity_id: str,
    *,
    new_money: Decimal,
    pre_money: Decimal | None,
    price_per_share: Decimal | None,
    pool_top_up: int = 0,
    pool_timing: str = "pre",
) -> dict:
    # the pool shuffle: a pre-money top-up sits in the price denominator (and so
    # dilutes existing holders), a post-money one is created after the round
    # (out of the denominator, so it dilutes everyone, new investors included)
    pre_pool = pool_top_up if pool_timing != "post" else 0
    post_pool = pool_top_up if pool_timing == "post" else 0

    # structure (issued/options/pool) is price-independent; probe it first
    base = fully_diluted(db, entity_id, Decimal("1"))
    fd_core = base["issued_shares"] + base["option_shares"] + base["pool_unallocated"]
    fd_pre = fd_core + pre_pool
    if fd_pre <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No shares outstanding to model against")

    if price_per_share is not None:
        price = Decimal(price_per_share)
        pre_money = (price * fd_pre).quantize(Decimal("0.01"), ROUND_HALF_UP)
    elif pre_money is not None:
        price = (Decimal(pre_money) / Decimal(fd_pre)).quantize(Decimal("0.0001"), ROUND_HALF_UP)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide pre_money or price_per_share")
    if price <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Scenario price must be positive")

    fd = fully_diluted(db, entity_id, price)  # converts priced at the round
    new_shares = int(Decimal(new_money) / price)
    safe_shares = fd["convertible_shares"]
    # three stages (Pulley-style matrix): today -> after SAFEs convert -> after
    # the round; SAFE conversions land at the mid stage, new money (and any
    # post-money pool) at the last
    fd_mid = fd_pre + safe_shares
    fd_post = fd_mid + new_shares + post_pool
    rows = []
    for r in fd["rows"]:
        is_pool = r["name"] == POOL_ROW
        before = r["issued"] + r["options"] + (pre_pool if is_pool else 0)
        mid = before + r["converts"]
        after = mid + (post_pool if is_pool else 0)
        rows.append({
            "name": r["name"],
            "type": r["type"],
            "before": before,
            "before_pct": round(before / fd_pre * 100, 4),
            "after_safes_pct": round(mid / fd_mid * 100, 4) if fd_mid else 0.0,
            "after": after,
            "after_pct": round(after / fd_post * 100, 4) if fd_post else 0.0,
        })
    if pool_top_up and not any(r["name"] == POOL_ROW for r in fd["rows"]):
        rows.append({
            "name": POOL_ROW, "type": "pool",
            "before": pre_pool, "before_pct": round(pre_pool / fd_pre * 100, 4),
            "after_safes_pct": round(pre_pool / fd_mid * 100, 4) if fd_mid else 0.0,
            "after": pool_top_up, "after_pct": round(pool_top_up / fd_post * 100, 4) if fd_post else 0.0,
        })
    rows.append({
        "name": "New investors (this round)", "type": "investor",
        "before": 0, "before_pct": 0.0, "after_safes_pct": 0.0,
        "after": new_shares, "after_pct": round(new_shares / fd_post * 100, 4) if fd_post else 0.0,
    })
    for r in rows:
        r["dilution_pct"] = round(r["after_pct"] - r["before_pct"], 4)
    rows.sort(key=lambda r: r["after"], reverse=True)

    return {
        "entity_id": entity_id,
        "price_per_share": str(price),
        "pre_money": str(Decimal(pre_money).quantize(Decimal("0.01"), ROUND_HALF_UP)),
        "new_money": str(Decimal(new_money).quantize(Decimal("0.01"), ROUND_HALF_UP)),
        "post_money": str((Decimal(pre_money) + Decimal(new_money)).quantize(Decimal("0.01"), ROUND_HALF_UP)),
        "pool_top_up": pool_top_up,
        "pool_timing": pool_timing,
        "new_shares": new_shares,
        "safe_shares_converted": safe_shares,
        "excluded_instruments": fd["excluded_instruments"],
        "fd_pre": fd_pre,
        "fd_post": fd_post,
        "rows": rows,
    }


def _round_price(fd_pre: int, pre_money, price_per_share) -> Decimal:
    """Shared price derivation: an explicit price wins, else pre-money / FD."""
    if price_per_share is not None:
        price = Decimal(price_per_share).quantize(PRICE4, ROUND_HALF_UP)
    elif pre_money is not None:
        price = (Decimal(pre_money) / Decimal(fd_pre)).quantize(PRICE4, ROUND_HALF_UP)
    else:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Provide pre_money or price_per_share")
    if price <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Scenario price must be positive")
    return price


def plan_round(
    db: Session,
    entity_id: str,
    *,
    pre_money: Decimal | None,
    price_per_share: Decimal | None,
    tiers: list,
    pool_top_up: int = 0,
    pool_timing: str = "pre",
    apply_anti_dilution: bool = True,
) -> dict:
    """Interactive round planner (FR-C-4): a pro-forma round with MULTIPLE
    investor tiers (each optionally split among co-investors), the down-round
    anti-dilution adjustment folded into the post-round table, and outstanding
    SAFEs converting at the round — all as a projection, never written.

    Each tier is a leaf allocation (name + amount) unless it carries
    co-investors, in which case each co-investor is its own leaf. Shares =
    amount / price. Anti-dilution issues extra shares to protected preferred
    classes when the price is below their original issue price, diluting
    everyone else further."""
    pre_pool = pool_top_up if pool_timing != "post" else 0
    post_pool = pool_top_up if pool_timing == "post" else 0

    base = fully_diluted(db, entity_id, Decimal("1"))
    fd_core = base["issued_shares"] + base["option_shares"] + base["pool_unallocated"]
    fd_pre = fd_core + pre_pool
    if fd_pre <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No shares outstanding to model against")

    price = _round_price(fd_pre, pre_money, price_per_share)
    pre_money = (price * fd_pre).quantize(CENTS, ROUND_HALF_UP)
    fd = fully_diluted(db, entity_id, price)

    # flatten tiers into leaf allocations (co-investors split a tier)
    leaves = []
    for t in tiers:
        subs = [c for c in (t.co_investors or []) if Decimal(c.amount) > 0]
        if subs:
            for c in subs:
                amt = Decimal(c.amount)
                leaves.append({"tier": t.name, "name": c.name, "amount": amt, "shares": int(amt / price)})
        elif Decimal(t.amount) > 0:
            amt = Decimal(t.amount)
            leaves.append({"tier": t.name, "name": t.name, "amount": amt, "shares": int(amt / price)})
    new_money = sum((leaf["amount"] for leaf in leaves), Decimal("0"))
    new_shares_total = sum(leaf["shares"] for leaf in leaves)

    safe_shares = fd["convertible_shares"]
    fd_mid = fd_pre + safe_shares

    # anti-dilution: extra shares to protected classes on a down round
    ad_extra_by_sh: dict[str, int] = {}
    anti_dilution: list[dict] = []
    if apply_anti_dilution and new_shares_total > 0:
        for sc in db.query(SecurityClass).filter_by(entity_id=entity_id):
            if sc.anti_dilution == "none" or not sc.orig_issue_price or Decimal(sc.orig_issue_price) <= 0:
                continue
            prev = anti_dilution_preview(db, sc, price, new_shares_total)
            total_extra = sum(h["additional_shares"] for h in prev["holders"])
            if total_extra <= 0:
                continue  # not a down round for this class
            for h in prev["holders"]:
                if h["additional_shares"]:
                    ad_extra_by_sh[h["stakeholder_id"]] = (
                        ad_extra_by_sh.get(h["stakeholder_id"], 0) + h["additional_shares"]
                    )
            anti_dilution.append({
                "security_class": sc.name,
                "method": sc.anti_dilution,
                "orig_issue_price": prev["orig_issue_price"],
                "adjusted_price": prev["adjusted_price"],
                "additional_shares": total_extra,
            })
    ad_total = sum(ad_extra_by_sh.values())

    fd_post = fd_mid + new_shares_total + post_pool + ad_total

    rows = []
    for r in fd["rows"]:
        is_pool = r["name"] == POOL_ROW
        before = r["issued"] + r["options"] + (pre_pool if is_pool else 0)
        mid = before + r["converts"]
        ad = ad_extra_by_sh.get(r.get("stakeholder_id"), 0)
        after = mid + (post_pool if is_pool else 0) + ad
        rows.append({
            "name": r["name"], "type": r["type"], "tier": None,
            "before": before, "before_pct": round(before / fd_pre * 100, 4),
            "after_safes_pct": round(mid / fd_mid * 100, 4) if fd_mid else 0.0,
            "anti_dilution_shares": ad,
            "after": after, "after_pct": round(after / fd_post * 100, 4) if fd_post else 0.0,
        })
    if pool_top_up and not any(r["name"] == POOL_ROW for r in fd["rows"]):
        rows.append({
            "name": POOL_ROW, "type": "pool", "tier": None,
            "before": pre_pool, "before_pct": round(pre_pool / fd_pre * 100, 4),
            "after_safes_pct": round(pre_pool / fd_mid * 100, 4) if fd_mid else 0.0,
            "anti_dilution_shares": 0,
            "after": pool_top_up, "after_pct": round(pool_top_up / fd_post * 100, 4) if fd_post else 0.0,
        })
    for leaf in leaves:
        rows.append({
            "name": leaf["name"], "type": "investor", "tier": leaf["tier"],
            "before": 0, "before_pct": 0.0, "after_safes_pct": 0.0, "anti_dilution_shares": 0,
            "after": leaf["shares"],
            "after_pct": round(leaf["shares"] / fd_post * 100, 4) if fd_post else 0.0,
        })
    for r in rows:
        r["dilution_pct"] = round(r["after_pct"] - r["before_pct"], 4)
    rows.sort(key=lambda r: r["after"], reverse=True)

    return {
        "entity_id": entity_id,
        "price_per_share": str(price),
        "pre_money": str(pre_money),
        "new_money": str(new_money.quantize(CENTS, ROUND_HALF_UP)),
        "post_money": str((pre_money + new_money).quantize(CENTS, ROUND_HALF_UP)),
        "pool_top_up": pool_top_up,
        "pool_timing": pool_timing,
        "new_shares": new_shares_total,
        "safe_shares_converted": safe_shares,
        "anti_dilution_shares": ad_total,
        "anti_dilution": anti_dilution,
        "excluded_instruments": fd["excluded_instruments"],
        "fd_pre": fd_pre,
        "fd_post": fd_post,
        "rows": rows,
    }

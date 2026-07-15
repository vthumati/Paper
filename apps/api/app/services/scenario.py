"""Round scenario modeling (FR-C-4): the pro-forma cap table for a
HYPOTHETICAL round — nothing is written to the ledger.

Conventions (the market-standard ones):
 - the pre-money is divided by the pre-round fully-diluted share count
   (issued + unexercised options + unallocated pool + any pool top-up) to get
   the price; alternatively the caller supplies the price directly.
 - a pool top-up is created pre-money, so it dilutes existing holders only.
 - outstanding SAFEs/notes convert at the round (discount/cap terms applied
   at the scenario price) alongside the new money.
"""
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from .diluted import POOL_ROW, fully_diluted


def model_round(
    db: Session,
    entity_id: str,
    *,
    new_money: Decimal,
    pre_money: Decimal | None,
    price_per_share: Decimal | None,
    pool_top_up: int = 0,
) -> dict:
    # structure (issued/options/pool) is price-independent; probe it first
    base = fully_diluted(db, entity_id, Decimal("1"))
    fd_pre = base["issued_shares"] + base["option_shares"] + base["pool_unallocated"] + pool_top_up
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
    fd_post = fd_pre + safe_shares + new_shares

    # three stages (Pulley-style matrix): today -> after SAFEs convert -> after
    # the round; SAFE conversions land at the mid stage, new money at the last
    fd_mid = fd_pre + safe_shares
    rows = []
    for r in fd["rows"]:
        before = r["issued"] + r["options"] + (pool_top_up if r["name"] == POOL_ROW else 0)
        after = before + r["converts"]
        rows.append({
            "name": r["name"],
            "type": r["type"],
            "before": before,
            "before_pct": round(before / fd_pre * 100, 4),
            "after_safes_pct": round(after / fd_mid * 100, 4) if fd_mid else 0.0,
            "after": after,
            "after_pct": round(after / fd_post * 100, 4) if fd_post else 0.0,
        })
    if pool_top_up and not any(r["name"] == POOL_ROW for r in fd["rows"]):
        rows.append({
            "name": POOL_ROW, "type": "pool",
            "before": pool_top_up, "before_pct": round(pool_top_up / fd_pre * 100, 4),
            "after_safes_pct": round(pool_top_up / fd_mid * 100, 4) if fd_mid else 0.0,
            "after": pool_top_up, "after_pct": round(pool_top_up / fd_post * 100, 4),
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
        "new_shares": new_shares,
        "safe_shares_converted": safe_shares,
        "excluded_instruments": fd["excluded_instruments"],
        "fd_pre": fd_pre,
        "fd_post": fd_post,
        "rows": rows,
    }

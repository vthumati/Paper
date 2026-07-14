"""Fully-diluted cap table (FR-C): the issued cap table plus everything that
can become shares — unexercised option grants, the unallocated ESOP pool, and
outstanding SAFEs/notes converted at an assumed price (defaults to the current
FMV). Instruments that cannot be priced are listed as excluded, not guessed.

Like the issued cap table (ADR-2) this is a computed projection, never stored.
"""
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.captable import SecurityClass, Stakeholder
from ..models.esop import ESOPScheme, Grant
from ..models.instruments import ConvertibleInstrument, InstrumentStatus
from . import valuation as valsvc
from .captable import _positions
from .esop import exercised_by_grant
from .instruments import conversion_preview
from .money import PRICE4

POOL_ROW = "ESOP pool (unallocated)"


def fully_diluted(db: Session, entity_id: str, assumed_price: Decimal | None) -> dict:
    today = today_ist()
    holders = {s.id: s for s in db.query(Stakeholder).filter_by(entity_id=entity_id)}

    # keyed by stakeholder id, or by display name for holders not yet on the register
    rows: dict[str, dict] = {}

    def row(key: str, name: str | None, typ: str | None):
        return rows.setdefault(
            key, {"stakeholder_id": key if key in holders else None, "name": name,
                  "type": typ, "issued": 0, "options": 0, "converts": 0}
        )

    # 1) issued shares (all classes aggregated per holder)
    for (sh_id, _cls), p in _positions(db, entity_id).items():
        if p["quantity"] <= 0:
            continue
        sh = holders.get(sh_id)
        r = row(sh_id, sh.name if sh else None, sh.type.value if sh else None)
        r["issued"] += p["quantity"]

    # 2) granted-but-unexercised options + unallocated pool
    granted = 0
    exercised = exercised_by_grant(db, entity_id)
    for g in db.query(Grant).filter_by(entity_id=entity_id):
        granted += g.quantity
        outstanding = g.quantity - exercised.get(g.id, 0)
        if outstanding <= 0:
            continue
        sh = holders.get(g.stakeholder_id)
        r = row(g.stakeholder_id, sh.name if sh else None, sh.type.value if sh else None)
        r["options"] += outstanding
    pool_total = sum(s.pool_size for s in db.query(ESOPScheme).filter_by(entity_id=entity_id))
    pool_unallocated = max(0, pool_total - granted)
    if pool_unallocated:
        row(POOL_ROW, POOL_ROW, "pool")["options"] = pool_unallocated

    # 3) outstanding convertibles at the assumed price (or current FMV);
    # issued total from step 1 prices any valuation cap without a re-replay
    issued_total = sum(r["issued"] for r in rows.values())
    price = assumed_price if assumed_price and assumed_price > 0 else valsvc.current_fmv(db, entity_id, today)
    excluded: list[str] = []
    by_name = {s.name: s for s in holders.values()}
    for inst in db.query(ConvertibleInstrument).filter_by(
        entity_id=entity_id, status=InstrumentStatus.OUTSTANDING
    ):
        if price is None:
            excluded.append(inst.investor_name)
            continue
        shares = conversion_preview(db, inst, price, today, total_shares=issued_total)["shares"]
        sh = by_name.get(inst.investor_name)
        key = sh.id if sh else inst.investor_name
        r = row(key, inst.investor_name, sh.type.value if sh else "investor")
        r["converts"] += shares

    out_rows = []
    fd_total = sum(r["issued"] + r["options"] + r["converts"] for r in rows.values())
    for r in rows.values():
        total = r["issued"] + r["options"] + r["converts"]
        out_rows.append(
            {**r, "total": total,
             "pct": round(total / fd_total * 100, 4) if fd_total else 0.0}
        )
    out_rows.sort(key=lambda r: r["total"], reverse=True)
    return {
        "entity_id": entity_id,
        "assumed_price": str(price) if price is not None else None,
        "issued_shares": sum(r["issued"] for r in rows.values()),
        "option_shares": sum(r["options"] for r in rows.values()) - pool_unallocated,
        "pool_unallocated": pool_unallocated,
        "convertible_shares": sum(r["converts"] for r in rows.values()),
        "fully_diluted_shares": fd_total,
        "rows": out_rows,
        "excluded_instruments": excluded,
    }


def anti_dilution_preview(
    db: Session, sc: SecurityClass, new_price: Decimal, new_shares: int
) -> dict:
    """Down-round adjustment for a protected preferred class (FR-C).

    broad_based: CP2 = CP1 × (A + B) / (A + C), where A = fully-diluted shares
    before the round, B = new money / CP1, C = new shares issued.
    full_ratchet: CP2 = new round price.
    Holders convert at CP1/CP2 : 1, so each gets held × (ratio − 1) extra
    shares on conversion. A preview — nothing is written to the ledger."""
    if sc.anti_dilution == "none":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Class has no anti-dilution protection")
    if not sc.orig_issue_price or Decimal(sc.orig_issue_price) <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Class has no original issue price set")
    if new_price <= 0 or new_shares <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "new_price and new_shares must be positive")

    cp1 = Decimal(sc.orig_issue_price)
    if new_price >= cp1:
        cp2 = cp1  # not a down round — no adjustment
    elif sc.anti_dilution == "full_ratchet":
        cp2 = new_price
    else:
        a = Decimal(fully_diluted(db, sc.entity_id, new_price)["fully_diluted_shares"])
        b = new_price * Decimal(new_shares) / cp1
        c = Decimal(new_shares)
        cp2 = cp1 * (a + b) / (a + c) if a + c > 0 else cp1
    cp2 = cp2.quantize(PRICE4, ROUND_HALF_UP)
    ratio = cp1 / cp2 if cp2 > 0 else Decimal("1")

    holders = {s.id: s for s in db.query(Stakeholder).filter_by(entity_id=sc.entity_id)}
    affected = []
    for (sh_id, cls_id), p in _positions(db, sc.entity_id).items():
        if cls_id != sc.id or p["quantity"] <= 0:
            continue
        extra = int(p["quantity"] * (ratio - Decimal("1")))
        sh = holders.get(sh_id)
        affected.append(
            {"stakeholder_id": sh_id, "stakeholder_name": sh.name if sh else None,
             "held": p["quantity"], "additional_shares": extra}
        )
    affected.sort(key=lambda r: r["held"], reverse=True)
    return {
        "security_class_id": sc.id,
        "method": sc.anti_dilution,
        "orig_issue_price": str(cp1),
        "new_price": str(new_price),
        "adjusted_price": str(cp2),
        "conversion_ratio": str(ratio.quantize(Decimal("0.000001"), ROUND_HALF_UP)),
        "holders": affected,
    }

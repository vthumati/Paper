"""Cap-table projection (ADR-2): derive the live cap table from the
append-only ledger of issuances, transfers, conversions and buybacks.

Positions are computed per (stakeholder, security_class) by replaying every
event in chronological order, carrying a cost basis that follows the shares
(so liquidation preference is correct after secondary transfers)."""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import event
from sqlalchemy.orm import Session

from ..models.captable import (
    BuybackTransaction,
    ConversionEvent,
    CorporateAction,
    CorporateActionType,
    IssuanceTransaction,
    SecurityClass,
    Stakeholder,
    TransferTransaction,
)

from .money import CENTS  # shared paise quantisation

# Uniform stamp duty on transfer of shares: 0.015% of consideration.
TRANSFER_STAMP_DUTY_RATE = Decimal("0.00015")


def stamp_duty_on_transfer(consideration: Decimal) -> Decimal:
    return (Decimal(consideration) * TRANSFER_STAMP_DUTY_RATE).quantize(CENTS, ROUND_HALF_UP)


def _ordered_events(db: Session, entity_id: str):
    """Yield (sort_key, kind, row) for every ledger event of the entity."""
    events = []
    for t in db.query(IssuanceTransaction).filter_by(entity_id=entity_id):
        events.append(((t.issue_date, t.created_at), "issue", t))
    for t in db.query(TransferTransaction).filter_by(entity_id=entity_id):
        events.append(((t.transfer_date, t.created_at), "transfer", t))
    for t in db.query(ConversionEvent).filter_by(entity_id=entity_id):
        events.append(((t.date, t.created_at), "conversion", t))
    for t in db.query(BuybackTransaction).filter_by(entity_id=entity_id):
        events.append(((t.date, t.created_at), "buyback", t))
    for t in db.query(CorporateAction).filter_by(entity_id=entity_id):
        events.append(((t.date, t.created_at), "corporate_action", t))
    events.sort(key=lambda e: e[0])
    return events


_POS_CACHE = "_captable_positions"  # per-Session memo of replayed positions


def _positions(db: Session, entity_id: str) -> dict:
    """Live positions for an entity, replayed from the ledger.

    Memoised per request: the same entity's positions are replayed once, even
    when several call sites need them (dashboard, portal loops, fully-diluted,
    holding checks). The memo is skipped whenever the session has pending
    writes (so a write path that appends events mid-operation always sees fresh
    numbers — autoflush surfaces the pending rows) and is cleared on every flush
    (see `_clear_positions_cache`). The append-only ledger stays the source of
    truth — this only avoids redundant replays within one read request.

    Consumers must treat the result as read-only (it may be a shared object)."""
    if db.new or db.dirty or db.deleted:
        return _compute_positions(db, entity_id)
    cache = db.info.setdefault(_POS_CACHE, {})
    if entity_id not in cache:
        cache[entity_id] = _compute_positions(db, entity_id)
    return cache[entity_id]


def _compute_positions(db: Session, entity_id: str) -> dict:
    """{(stakeholder_id, class_id): {'quantity': int, 'amount': Decimal}}"""
    pos: dict[tuple[str, str], dict] = {}

    def cell(sh, cls):
        return pos.setdefault((sh, cls), {"quantity": 0, "amount": Decimal("0")})

    def basis_per_share(c):
        return (c["amount"] / c["quantity"]) if c["quantity"] else Decimal("0")

    for _key, kind, e in _ordered_events(db, entity_id):
        if kind == "issue":
            c = cell(e.stakeholder_id, e.security_class_id)
            c["quantity"] += e.quantity
            c["amount"] += Decimal(e.quantity) * (e.price_per_unit or Decimal("0"))
        elif kind == "transfer":
            src = cell(e.from_stakeholder_id, e.security_class_id)
            moved = basis_per_share(src) * e.quantity
            src["quantity"] -= e.quantity
            src["amount"] -= moved
            dst = cell(e.to_stakeholder_id, e.security_class_id)
            dst["quantity"] += e.quantity
            dst["amount"] += moved  # original cost basis follows the shares
        elif kind == "conversion":
            src = cell(e.stakeholder_id, e.from_class_id)
            moved = basis_per_share(src) * e.from_quantity
            src["quantity"] -= e.from_quantity
            src["amount"] -= moved
            dst = cell(e.stakeholder_id, e.to_class_id)
            dst["quantity"] += e.to_quantity
            dst["amount"] += moved
        elif kind == "buyback":
            c = cell(e.stakeholder_id, e.security_class_id)
            c["amount"] -= basis_per_share(c) * e.quantity
            c["quantity"] -= e.quantity
        elif kind == "corporate_action":
            # apply class-wide to every holder of that class; cost basis unchanged
            for (sh, cls), c in list(pos.items()):
                if cls != e.security_class_id or c["quantity"] <= 0:
                    continue
                if e.type == CorporateActionType.SPLIT:
                    c["quantity"] = c["quantity"] * e.numerator // e.denominator
                elif e.type == CorporateActionType.BONUS:
                    c["quantity"] += c["quantity"] * e.numerator // e.denominator
    return pos


def compute_cap_table(db: Session, entity_id: str) -> dict:
    classes = {c.id: c for c in db.query(SecurityClass).filter_by(entity_id=entity_id)}
    holders = {s.id: s for s in db.query(Stakeholder).filter_by(entity_id=entity_id)}
    pos = _positions(db, entity_id)

    total_shares = sum(p["quantity"] for p in pos.values() if p["quantity"] > 0)
    rows = []
    for (sh_id, sc_id), p in pos.items():
        if p["quantity"] <= 0:
            continue
        pct = (p["quantity"] / total_shares * 100) if total_shares else 0.0
        sh = holders.get(sh_id)
        sc = classes.get(sc_id)
        rows.append(
            {
                "stakeholder_id": sh_id,
                "stakeholder_name": sh.name if sh else None,
                "stakeholder_type": sh.type.value if sh else None,
                "security_class_id": sc_id,
                "security_class": sc.name if sc else None,
                "kind": sc.kind.value if sc else None,
                "quantity": p["quantity"],
                "amount_invested": str(p["amount"].quantize(CENTS, ROUND_HALF_UP)),
                "ownership_pct": round(pct, 4),
            }
        )
    rows.sort(key=lambda r: r["quantity"], reverse=True)
    total_invested = sum((Decimal(r["amount_invested"]) for r in rows), Decimal("0"))
    return {
        "entity_id": entity_id,
        "total_shares": total_shares,
        "total_invested": str(total_invested),
        "holders": rows,
    }


def holding_quantity(db: Session, entity_id: str, stakeholder_id: str, class_id: str) -> int:
    return _positions(db, entity_id).get((stakeholder_id, class_id), {"quantity": 0})["quantity"]


def waterfall_range(db: Session, entity_id: str, exit_amounts: list[Decimal]) -> dict:
    """Per-holder proceeds across several exit values — shows where the
    preference stack flips to pro-rata (FR-C-5)."""
    columns = [liquidation_waterfall(db, entity_id, a) for a in exit_amounts]
    holders: dict[str, dict] = {}
    for col_idx, col in enumerate(columns):
        for p in col["payouts"]:
            h = holders.setdefault(
                p["stakeholder_id"],
                {"stakeholder_id": p["stakeholder_id"],
                 "stakeholder_name": p["stakeholder_name"],
                 "payouts": ["0.00"] * len(columns)},
            )
            h["payouts"][col_idx] = p["payout"]
    rows = sorted(holders.values(), key=lambda h: Decimal(h["payouts"][-1]), reverse=True)
    return {
        "entity_id": entity_id,
        "exit_amounts": [c["exit_amount"] for c in columns],
        "rows": rows,
    }


def liquidation_waterfall(db: Session, entity_id: str, exit_amount: Decimal) -> dict:
    """Distribute an exit amount: preferred liquidation preferences first (by
    seniority, pro-rated within a tier if short), then the remainder pro-rata
    by shares to common + participating preferred.

    Simplification: the as-converted election for non-participating preferred
    (take preference vs convert to common) is not yet modelled."""
    classes = {c.id: c for c in db.query(SecurityClass).filter_by(entity_id=entity_id)}
    holders = {s.id: s for s in db.query(Stakeholder).filter_by(entity_id=entity_id)}
    pos = _positions(db, entity_id)

    holdings = []
    for (sh_id, sc_id), p in pos.items():
        if p["quantity"] <= 0:
            continue
        sc = classes.get(sc_id)
        holdings.append(
            {
                "sh_id": sh_id,
                "qty": p["quantity"],
                "invested": p["amount"],
                "pref_multiple": Decimal(sc.pref_multiple) if sc else Decimal("0"),
                "participating": bool(sc.participating) if sc else False,
                "seniority": sc.seniority if sc else 0,
            }
        )

    remaining = Decimal(exit_amount)
    payout: dict[str, Decimal] = {}

    def add(sh_id, amt):
        payout[sh_id] = payout.get(sh_id, Decimal("0")) + amt

    preferred = [h for h in holdings if h["pref_multiple"] > 0]
    for tier in sorted({h["seniority"] for h in preferred}, reverse=True):
        tier_holders = [h for h in preferred if h["seniority"] == tier]
        claims = {id(h): h["pref_multiple"] * h["invested"] for h in tier_holders}
        total_claim = sum(claims.values())
        if total_claim <= 0:
            continue
        if remaining >= total_claim:
            for h in tier_holders:
                add(h["sh_id"], claims[id(h)])
            remaining -= total_claim
        else:  # short — pro-rate within the tier
            for h in tier_holders:
                add(h["sh_id"], remaining * claims[id(h)] / total_claim)
            remaining = Decimal("0")
            break

    # remainder to common + participating preferred, pro-rata by shares
    pool = [h for h in holdings if h["pref_multiple"] == 0 or h["participating"]]
    total_pool_shares = sum(h["qty"] for h in pool)
    if remaining > 0 and total_pool_shares > 0:
        for h in pool:
            add(h["sh_id"], remaining * Decimal(h["qty"]) / Decimal(total_pool_shares))

    rows = [
        {
            "stakeholder_id": sh_id,
            "stakeholder_name": holders[sh_id].name if sh_id in holders else None,
            "payout": str(amt.quantize(CENTS, ROUND_HALF_UP)),
        }
        for sh_id, amt in payout.items()
    ]
    rows.sort(key=lambda r: Decimal(r["payout"]), reverse=True)
    return {
        "entity_id": entity_id,
        "exit_amount": str(Decimal(exit_amount).quantize(CENTS, ROUND_HALF_UP)),
        "distributed": str(sum((Decimal(r["payout"]) for r in rows), Decimal("0"))),
        "payouts": rows,
    }


@event.listens_for(Session, "after_flush")
def _clear_positions_cache(session: Session, flush_context) -> None:
    """Any write flush invalidates the memoised positions, so the next read
    replays the (now changed) ledger. Reads never flush, so the memo survives
    across the many position lookups in a single read request."""
    session.info.pop(_POS_CACHE, None)

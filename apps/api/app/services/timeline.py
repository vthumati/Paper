"""Narrative cap-table timeline (FR-C-10): every equity event of an entity
rendered as a human-readable sentence, newest first — the founder-facing
"cap-table story" view, as opposed to the raw HTTP audit log (NFR-4)."""
import datetime
from decimal import Decimal

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
from ..models.esop import ExerciseTransaction, Grant
from ..models.instruments import ConvertibleInstrument, InstrumentType
from ..models.round import Round, RoundStatus
from ..models.valuation import ValuationReport, ValuationStatus


def _qty(n: int) -> str:
    return f"{n:,}"


def _money(v) -> str:
    d = Decimal(v or 0)
    if d == d.to_integral_value():
        return f"{int(d):,}"
    return f"{d.normalize():f}"


def entity_timeline(db: Session, entity_id: str) -> list[dict]:
    classes = {c.id: c for c in db.query(SecurityClass).filter_by(entity_id=entity_id)}
    holders = {s.id: s.name for s in db.query(Stakeholder).filter_by(entity_id=entity_id)}

    def cls(cid: str) -> str:
        c = classes.get(cid)
        return c.name if c else "?"

    def who(sid: str | None) -> str:
        return holders.get(sid, "Unknown") if sid else "Unknown"

    events: list[dict] = []

    def add(row_id: str, date: datetime.date, created, kind: str, text: str):
        events.append({"id": row_id, "date": date, "kind": kind, "text": text, "_c": created})

    for t in db.query(IssuanceTransaction).filter_by(entity_id=entity_id):
        text = f"{who(t.stakeholder_id)} received {_qty(t.quantity)} {cls(t.security_class_id)} shares"
        if t.price_per_unit and Decimal(t.price_per_unit) > 0:
            text += f" at ₹{_money(t.price_per_unit)} per share"
        add(t.id, t.issue_date, t.created_at, "issue", text)

    for t in db.query(TransferTransaction).filter_by(entity_id=entity_id):
        add(
            t.id, t.transfer_date, t.created_at, "transfer",
            f"{who(t.from_stakeholder_id)} transferred {_qty(t.quantity)} "
            f"{cls(t.security_class_id)} shares to {who(t.to_stakeholder_id)}"
            + (
                f" at ₹{_money(t.price_per_unit)} per share"
                if t.price_per_unit and Decimal(t.price_per_unit) > 0
                else ""
            ),
        )

    for t in db.query(ConversionEvent).filter_by(entity_id=entity_id):
        add(
            t.id, t.date, t.created_at, "conversion",
            f"{who(t.stakeholder_id)} converted {_qty(t.from_quantity)} {cls(t.from_class_id)} "
            f"into {_qty(t.to_quantity)} {cls(t.to_class_id)}",
        )

    for t in db.query(BuybackTransaction).filter_by(entity_id=entity_id):
        add(
            t.id, t.date, t.created_at, "buyback",
            f"The company bought back {_qty(t.quantity)} {cls(t.security_class_id)} shares "
            f"from {who(t.stakeholder_id)}",
        )

    for t in db.query(CorporateAction).filter_by(entity_id=entity_id):
        action = (
            f"Stock split {t.numerator}:{t.denominator}"
            if t.type == CorporateActionType.SPLIT
            else f"Bonus issue {t.numerator}:{t.denominator}"
        )
        add(t.id, t.date, t.created_at, "corporate_action", f"{action} on {cls(t.security_class_id)}")

    for inst in db.query(ConvertibleInstrument).filter_by(entity_id=entity_id):
        label = "SAFE" if inst.instrument_type == InstrumentType.SAFE else "convertible note"
        text = f"{inst.investor_name} invested ₹{_money(inst.principal)} via a {label}"
        if inst.valuation_cap:
            text += f" (cap ₹{_money(inst.valuation_cap)})"
        add(inst.id, inst.issue_date, inst.created_at, "instrument", text)

    for g in db.query(Grant).filter_by(entity_id=entity_id):
        add(
            g.id, g.grant_date, g.created_at, "grant",
            f"{who(g.stakeholder_id)} was granted {_qty(g.quantity)} options "
            f"at ₹{_money(g.exercise_price)} strike ({g.total_months}-month vesting)",
        )

    grant_holder = {g.id: g.stakeholder_id for g in db.query(Grant).filter_by(entity_id=entity_id)}
    for ex in db.query(ExerciseTransaction).filter_by(entity_id=entity_id):
        add(
            ex.id, ex.date, ex.created_at, "exercise",
            f"{who(grant_holder.get(ex.grant_id))} exercised {_qty(ex.quantity)} options "
            f"at ₹{_money(ex.exercise_price)}",
        )

    for v in db.query(ValuationReport).filter_by(entity_id=entity_id, status=ValuationStatus.FINAL):
        text = f"FMV set at ₹{_money(v.fmv_per_share)} per share ({v.method.value})"
        if v.valuer_name:
            text += f" by {v.valuer_name}"
        add(v.id, v.valuation_date, v.created_at, "valuation", text)

    for r in db.query(Round).filter_by(entity_id=entity_id):
        state = "closed" if r.status == RoundStatus.CLOSED else "opened"
        text = f"Round “{r.name}” {state}"
        if r.target_amount and Decimal(r.target_amount) > 0:
            text += f" — target ₹{_money(r.target_amount)}"
        add(r.id, r.created_at.date(), r.created_at, "round", text)

    events.sort(key=lambda e: (e["date"], e["_c"]), reverse=True)
    for e in events:
        e.pop("_c")
    return events

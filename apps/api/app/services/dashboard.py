"""Unified entity dashboard (FR-T-3) — aggregates state across modules into
one home view."""

from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.compliance import ComplianceObligation, ObligationStatus
from ..models.dataroom import DataRoom
from ..models.document import Document
from ..models.entity import Incorporation, LegalEntity
from ..models.esop import ESOPScheme, Grant
from ..models.fund import Fund, PortfolioInvestment
from ..models.governance import Meeting, Resolution, ResolutionStatus
from ..models.round import Round, RoundStatus
from ..models.valuation import ValuationReport, ValuationStatus
from .captable import compute_cap_table
from .fund import capital_accounts
from .fund_perf import fund_performance
from .valuation import current_valuation

_OPEN = {ObligationStatus.DUE, ObligationStatus.IN_PREP}


def _by_class(ct: dict) -> list[dict]:
    """Aggregate the cap table by security class for the ownership donut."""
    agg: dict[str, dict] = {}
    for h in ct["holders"]:
        key = h["security_class"] or "?"
        row = agg.setdefault(key, {"name": key, "kind": h["kind"], "quantity": 0})
        row["quantity"] += h["quantity"]
    total = ct["total_shares"]
    rows = sorted(agg.values(), key=lambda r: r["quantity"], reverse=True)
    for r in rows:
        r["pct"] = round(r["quantity"] / total * 100, 2) if total else 0.0
    return rows


def _capital(db: Session, entity_id: str, ct: dict, grants: list[Grant], pool: int) -> dict:
    """Authorized vs issued share capital. Authorized shares are derived from
    the incorporation charter (authorised capital / par value) when the entity
    was created through the wizard; otherwise unknown."""
    authorized = None
    inc = db.query(Incorporation).filter_by(entity_id=entity_id).first()
    if inc and inc.par_value and inc.par_value > 0:
        authorized = int(inc.authorised_capital / inc.par_value)
    issued = ct["total_shares"]
    return {
        "authorized_shares": authorized,
        "issued": issued,
        "available": max(0, authorized - issued) if authorized is not None else None,
        "esop_pool": pool,
        "esop_granted": sum(g.quantity for g in grants),
    }


def _valuation(db: Session, entity_id: str, today) -> dict:
    v = current_valuation(db, entity_id, today)
    if v is not None:
        return {
            "status": "active",
            "fmv_per_share": str(v.fmv_per_share),
            "method": v.method.value,
            "valuation_date": v.valuation_date.isoformat(),
            "valid_until": v.valid_until.isoformat() if v.valid_until else None,
            "valuer_name": v.valuer_name,
        }
    has_final = (
        db.query(ValuationReport)
        .filter_by(entity_id=entity_id, status=ValuationStatus.FINAL)
        .count()
        > 0
    )
    return {
        "status": "expired" if has_final else "missing",
        "fmv_per_share": None,
        "method": None,
        "valuation_date": None,
        "valid_until": None,
        "valuer_name": None,
    }


def entity_dashboard(db: Session, entity: LegalEntity) -> dict:
    eid = entity.id
    today = today_ist()

    ct = compute_cap_table(db, eid)
    rounds = db.query(Round).filter_by(entity_id=eid).all()
    obs = db.query(ComplianceObligation).filter_by(entity_id=eid).all()
    overdue = sum(1 for o in obs if o.status in _OPEN and o.due_date < today)
    grants = db.query(Grant).filter_by(entity_id=eid).all()
    resolutions = db.query(Resolution).filter_by(entity_id=eid).all()

    pool = sum(s.pool_size for s in db.query(ESOPScheme).filter_by(entity_id=eid))

    out = {
        "entity": {"id": eid, "name": entity.name, "type": entity.type.value},
        "cap_table": {
            "total_shares": ct["total_shares"],
            "total_invested": ct["total_invested"],
            "holders": len(ct["holders"]),
            "by_class": _by_class(ct),
        },
        "capital": _capital(db, eid, ct, grants, pool),
        "valuation": _valuation(db, eid, today),
        "fundraising": {
            "rounds": len(rounds),
            "open_rounds": sum(1 for r in rounds if r.status != RoundStatus.CLOSED),
        },
        "compliance": {"total": len(obs), "overdue": overdue},
        "esop": {
            "schemes": db.query(ESOPScheme).filter_by(entity_id=eid).count(),
            "options_granted": sum(g.quantity for g in grants),
        },
        "governance": {
            "meetings": db.query(Meeting).filter_by(entity_id=eid).count(),
            "pending_resolutions": sum(
                1 for r in resolutions if r.status == ResolutionStatus.DRAFT
            ),
        },
        "documents": db.query(Document).filter_by(entity_id=eid).count(),
        "data_rooms": db.query(DataRoom).filter_by(entity_id=eid).count(),
    }

    fund = db.query(Fund).filter_by(entity_id=eid).first()
    if fund:
        acc = capital_accounts(db, fund)
        perf = fund_performance(db, fund)
        out["fund"] = {
            "sebi_category": fund.sebi_category.value,
            "carry_pct": str(fund.carry_pct),
            "hurdle_pct": str(fund.hurdle_pct),
            "mgmt_fee_pct": str(fund.mgmt_fee_pct),
            "committed": acc["totals"]["committed"],
            "drawn": acc["totals"]["drawn"],
            "uncalled": acc["totals"]["remaining"],
            "distributed": acc["totals"]["distributed"],
            "lps": len(acc["accounts"]),
            "nav": perf["nav"],
            "tvpi": perf["tvpi"],
            "dpi": perf["dpi"],
            "portfolio_count": db.query(PortfolioInvestment).filter_by(fund_id=fund.id).count(),
        }
    return out

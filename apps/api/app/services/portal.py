"""Investor / LP portal service (FR-K). Builds a per-user dashboard from:
 - InvestorAccess grants matching the user's email -> company holdings + updates
 - LP records matching the user's email -> fund capital accounts
 - DataRoom access grants matching the email -> documents shared with them
 - SPV co-investor records matching the email -> syndicate deal positions
plus a portfolio summary aggregating across everything."""
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.captable import Stakeholder
from ..models.dataroom import DataRoom, DataRoomAccessGrant, DataRoomItem
from ..models.document import Document
from ..models.entity import LegalEntity
from ..models.esop import ExerciseRequest, Grant
from ..models.fund import LP, Fund
from ..models.governance import Resolution
from ..models.identity import User
from ..models.instruments import ConvertibleInstrument, InstrumentStatus
from ..models.portal import (
    InvestorAccess,
    InvestorConsent,
    InvestorUpdate,
    SecondaryRequest,
)
from ..models.spv import CoInvestor, SPV
from .captable import compute_cap_table
from .esop import grant_view, vesting_projection
from .fund import capital_accounts
from .fund_perf import fund_performance
from .valuation import current_fmv

from .money import CENTS  # shared paise quantisation


def _shared_documents(db: Session, entity_id: str, email: str) -> list[dict]:
    today = today_ist()
    docs = []
    for room in db.query(DataRoom).filter_by(entity_id=entity_id):
        grant = (
            db.query(DataRoomAccessGrant)
            .filter_by(data_room_id=room.id, email=email)
            .first()
        )
        if grant is None:
            continue
        if grant.expiry is not None and grant.expiry < today:
            continue  # access has expired (FR-I-1)
        for item in db.query(DataRoomItem).filter_by(data_room_id=room.id):
            d = db.get(Document, item.document_id)
            if d is not None:
                docs.append({"id": d.id, "title": d.title, "data_room": room.name})
    return docs


def _updates(db: Session, entity_id: str) -> list[dict]:
    return [
        {"id": u.id, "title": u.title, "body": u.body, "created_at": u.created_at}
        for u in db.query(InvestorUpdate)
        .filter_by(entity_id=entity_id)
        .order_by(InvestorUpdate.created_at.desc())
    ]


def portal_for_user(db: Session, user: User) -> dict:
    today = today_ist()
    companies = []
    total_invested = Decimal("0")
    portfolio_value = Decimal("0")
    for a in db.query(InvestorAccess).filter_by(email=user.email):
        entity = db.get(LegalEntity, a.entity_id)
        if entity is None:
            continue
        holdings = []
        value = Decimal("0")
        if a.stakeholder_id:
            ct = compute_cap_table(db, a.entity_id)
            holdings = [h for h in ct["holders"] if h["stakeholder_id"] == a.stakeholder_id]
            fmv = current_fmv(db, a.entity_id, today)
            for h in holdings:
                total_invested += Decimal(h["amount_invested"])
                # mark at latest FMV when the company has one; else hold at cost
                value += (
                    Decimal(h["quantity"]) * Decimal(fmv)
                    if fmv is not None
                    else Decimal(h["amount_invested"])
                )
        portfolio_value += value
        consents = []
        for c in db.query(InvestorConsent).filter_by(entity_id=a.entity_id, email=user.email):
            res = db.get(Resolution, c.resolution_id)
            consents.append(
                {"id": c.id, "title": res.title if res else None,
                 "type": res.type.value if res else None, "status": c.status.value}
            )
        sale_requests = []
        if a.stakeholder_id:
            sale_requests = [
                {"id": r.id, "quantity": r.quantity, "price_per_unit": str(r.price_per_unit),
                 "status": r.status.value}
                for r in db.query(SecondaryRequest).filter_by(
                    entity_id=a.entity_id, stakeholder_id=a.stakeholder_id
                )
            ]
        companies.append(
            {
                "entity_id": entity.id,
                "entity_name": entity.name,
                "entity_type": entity.type.value,
                "holdings": holdings,
                "current_value": str(value.quantize(CENTS, ROUND_HALF_UP)),
                "instruments": [],
                "consents": consents,
                "sale_requests": sale_requests,
                "access_id": a.id,
                "stakeholder_id": a.stakeholder_id,
                "documents": _shared_documents(db, entity.id, user.email),
                "updates": _updates(db, entity.id),
            }
        )

    # convertible holdings (e.g. family-and-friends SAFEs) matched by email —
    # visible even before conversion or an explicit portal grant
    by_entity = {c["entity_id"]: c for c in companies}
    for inst in db.query(ConvertibleInstrument).filter_by(investor_email=user.email):
        entity = db.get(LegalEntity, inst.entity_id)
        if entity is None:
            continue
        entry = by_entity.get(inst.entity_id)
        if entry is None:
            entry = {
                "entity_id": entity.id,
                "entity_name": entity.name,
                "entity_type": entity.type.value,
                "holdings": [],
                "current_value": "0.00",
                "instruments": [],
                "consents": [],
                "sale_requests": [],
                "access_id": None,
                "stakeholder_id": None,
                "documents": _shared_documents(db, entity.id, user.email),
                "updates": _updates(db, entity.id),
            }
            companies.append(entry)
            by_entity[entity.id] = entry
        entry["instruments"].append(
            {
                "id": inst.id,
                "instrument_type": inst.instrument_type.value,
                "investor_kind": inst.investor_kind,
                "principal": str(inst.principal),
                "valuation_cap": str(inst.valuation_cap) if inst.valuation_cap else None,
                "discount_pct": str(inst.discount_pct),
                "issue_date": inst.issue_date,
                "status": inst.status.value,
                "converted_shares": inst.converted_shares,
            }
        )
        if inst.status == InstrumentStatus.OUTSTANDING:
            total_invested += Decimal(inst.principal)
            portfolio_value += Decimal(inst.principal)  # unconverted: held at cost

    funds = []
    total_committed = Decimal("0")
    for lp in db.query(LP).filter_by(email=user.email):
        fund = db.get(Fund, lp.fund_id)
        if fund is None:
            continue
        entity = db.get(LegalEntity, fund.entity_id)
        acc = capital_accounts(db, fund)
        mine = next((x for x in acc["accounts"] if x["lp_id"] == lp.id), None)
        if mine:
            total_committed += Decimal(mine["committed"])
        funds.append(
            {
                "fund_id": fund.id,
                "fund_name": entity.name if entity else None,
                "sebi_category": fund.sebi_category.value,
                "account": mine,
                "performance": fund_performance(db, fund),
                # statements + tax forms generated for this LP surface here automatically
                "statements": [
                    {"id": d.id, "title": d.title, "created_at": d.created_at}
                    for d in db.query(Document)
                    .filter(
                        Document.entity_id == fund.entity_id,
                        Document.subject_type.in_(["lp_statement", "form_64c"]),
                        Document.subject_id == lp.id,
                    )
                    .order_by(Document.created_at.desc())
                ],
                "updates": _updates(db, fund.entity_id),
            }
        )

    # SPV deals: co-investor invitations/commitments matched by email (FR-S-3)
    spvs = []
    for ci in db.query(CoInvestor).filter_by(email=user.email):
        spv = db.get(SPV, ci.spv_id)
        if spv is None:
            continue
        entity = db.get(LegalEntity, spv.entity_id)
        spvs.append(
            {
                "co_investor_id": ci.id,
                "spv_name": entity.name if entity else None,
                "sponsor": spv.sponsor,
                "target_company": spv.target_company,
                "structure": spv.structure,
                "carry_pct": str(spv.carry_pct),
                "min_ticket": str(spv.min_ticket),
                "status": ci.status,
                "commitment": str(ci.commitment),
                "contributed": str(ci.contributed),
                "documents": [
                    {"id": d.id, "title": d.title, "status": d.status.value}
                    for d in db.query(Document).filter_by(
                        subject_type="co_investor", subject_id=ci.id
                    )
                ],
                "updates": _updates(db, spv.entity_id),
            }
        )
        total_committed += Decimal(ci.commitment)
        total_invested += Decimal(ci.contributed)
        portfolio_value += Decimal(ci.contributed)  # held at cost inside the SPV

    # employee equity: ESOP grants for stakeholders matching the user's email
    grants = []
    total_vested = 0
    total_exercisable = 0
    for sh in db.query(Stakeholder).filter_by(email=user.email):
        entity = db.get(LegalEntity, sh.entity_id)
        fmv = current_fmv(db, sh.entity_id, today)
        for g in db.query(Grant).filter_by(stakeholder_id=sh.id):
            gv = grant_view(db, g, today)
            unrealized = None
            if fmv is not None:
                per = max(Decimal("0"), Decimal(fmv) - Decimal(g.exercise_price))
                unrealized = str((per * gv["exercisable"]).quantize(CENTS, ROUND_HALF_UP))
            requests = [
                {"id": r.id, "quantity": r.quantity, "status": r.status.value}
                for r in db.query(ExerciseRequest).filter_by(grant_id=g.id)
            ]
            proj = vesting_projection(g, today)
            grants.append(
                {
                    "grant_id": g.id,
                    "exercise_requests": requests,
                    "entity_name": entity.name if entity else None,
                    "granted": gv["quantity"],
                    "vested": gv["vested"],
                    "exercised": gv["exercised"],
                    "exercisable": gv["exercisable"],
                    "exercise_price": str(g.exercise_price),
                    "grant_date": g.grant_date,
                    "current_fmv": str(fmv) if fmv is not None else None,
                    "unrealized_gain": unrealized,
                    "vesting_pct": round(gv["vested"] / gv["quantity"] * 100, 2)
                    if gv["quantity"]
                    else 0.0,
                    "full_vest_date": proj["full_vest_date"],
                    "next_vests": proj["next_vests"],
                }
            )
            total_vested += gv["vested"]
            total_exercisable += gv["exercisable"]

    moic = (
        str((portfolio_value / total_invested).quantize(Decimal("0.01"), ROUND_HALF_UP))
        if total_invested > 0
        else None
    )
    return {
        "summary": {
            "companies": len(companies),
            "funds": len(funds),
            "spvs": len(spvs),
            "total_invested": str(total_invested),
            "portfolio_value": str(portfolio_value.quantize(CENTS, ROUND_HALF_UP)),
            "moic": moic,
            "total_committed": str(total_committed),
            "options_vested": total_vested,
            "options_exercisable": total_exercisable,
        },
        "companies": companies,
        "funds": funds,
        "spvs": spvs,
        "equity_grants": grants,
    }

"""Investor / LP portal service (FR-K). Builds a per-user dashboard from:
 - InvestorAccess grants matching the user's email -> company holdings + updates
 - LP records matching the user's email -> fund capital accounts
 - DataRoom access grants matching the email -> documents shared with them
 - SPV co-investor records matching the email -> syndicate deal positions
plus a portfolio summary aggregating across everything."""
from decimal import ROUND_HALF_UP, Decimal

from fastapi import HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from ..clock import now_ist, today_ist
from ..models.captable import Stakeholder
from ..models.dataroom import DataRoom, DataRoomAccessGrant, DataRoomItem
from ..models.document import Document
from ..models.entity import LegalEntity
from ..models.esop import ExerciseRequest, Grant
from ..models.fund import LP, CapitalCall, DrawdownNotice, Fund
from ..models.governance import Resolution
from ..models.identity import User
from ..models.instruments import ConvertibleInstrument, InstrumentStatus
from ..models.portal import (
    InvestorAccess,
    InvestorConsent,
    InvestorUpdate,
    SecondaryRequest,
)
from ..models.valuation import ValuationReport, ValuationStatus
from ..models.spv import CoInvestor, SPV
from .captable import compute_cap_table
from .esop import (
    exercise_tax_estimate,
    grant_schedule,
    grant_value_summary,
    grant_view,
    vesting_projection,
)
from .fund import capital_accounts, lp_distribution_history, lp_look_through
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


def _liquidity_for_user(db: Session, user: User, today) -> list[dict]:
    """Open buyback/tender windows the user is eligible for — gathered across
    every entity where they hold shares (matched by stakeholder email), so both
    investors and employee shareholders see them regardless of portal grants."""
    from ..models.liquidity import LiquidityEvent, LiquidityEventStatus, Tender, TenderStatus

    out = []
    for sh in db.query(Stakeholder).filter_by(email=user.email):
        events = [
            ev
            for ev in db.query(LiquidityEvent).filter_by(
                entity_id=sh.entity_id, status=LiquidityEventStatus.OPEN
            )
            if ev.opens_on <= today <= ev.closes_on
        ]
        if not events:
            continue
        ct = compute_cap_table(db, sh.entity_id)
        holdings = [
            {"security_class_id": h["security_class_id"], "security_class": h["security_class"],
             "kind": h["kind"], "quantity": h["quantity"]}
            for h in ct["holders"]
            if h["stakeholder_id"] == sh.id and h["quantity"] > 0
        ]
        if not holdings:
            continue
        entity = db.get(LegalEntity, sh.entity_id)
        for ev in events:
            my_tendered = sum(
                t.quantity
                for t in db.query(Tender).filter_by(
                    event_id=ev.id, stakeholder_id=sh.id, status=TenderStatus.SUBMITTED
                )
            )
            out.append(
                {
                    "id": ev.id,
                    "name": ev.name,
                    "kind": ev.kind,
                    "entity_name": entity.name if entity else None,
                    "price_per_share": str(ev.price_per_share),
                    "closes_on": ev.closes_on.isoformat(),
                    "my_tendered": my_tendered,
                    "holdings": holdings,
                }
            )
    return out


def _updates(db: Session, entity_id: str, viewer_email: str) -> list[dict]:
    return [
        {
            "id": u.id,
            "title": u.title,
            "body": u.body,
            "period_label": u.period_label,
            "highlights": u.highlights,
            "lowlights": u.lowlights,
            "asks": u.asks,
            "metrics": u.metrics,
            "created_at": u.created_at,
        }
        for u in db.query(InvestorUpdate)
        .filter_by(entity_id=entity_id, status="published")
        .order_by(InvestorUpdate.created_at.desc())
        # audience is an optional email list; null = every invited investor
        if u.audience is None or viewer_email in u.audience
    ]


def can_view_update(db: Session, upd: InvestorUpdate, email: str) -> bool:
    """True if `email` may see a published update — mirrors the three paths
    _updates() surfaces updates through: company InvestorAccess, fund-LP
    membership (update on the fund's entity), and SPV co-investor (update on
    the SPV's entity). Used to gate engagement (view-count) recording."""
    if upd.status != "published":
        return False
    if upd.audience is not None and email not in upd.audience:
        return False
    if (
        db.query(InvestorAccess)
        .filter_by(entity_id=upd.entity_id, email=email)
        .first()
        is not None
    ):
        return True
    for lp in db.query(LP).filter_by(email=email):
        fund = db.get(Fund, lp.fund_id)
        if fund is not None and fund.entity_id == upd.entity_id:
            return True
    for ci in db.query(CoInvestor).filter_by(email=email):
        spv = db.get(SPV, ci.spv_id)
        if spv is not None and spv.entity_id == upd.entity_id:
            return True
    return False


def portfolio_value_history(db: Session, user: User) -> dict:
    """Marked value of the user's company equity holdings over time (FR-K):
    at each historical valuation date across their companies, value each
    holding at the FMV effective then (falling back to cost before a company's
    first valuation), summed across companies. Drives the portal value hero.

    Scope note: this is the equity-holdings series only — fund/SPV positions,
    held at cost with no time series, are excluded (and labelled as such in the
    UI), so this can differ from the all-in portfolio_value stat."""
    today = today_ist()
    holdings: dict[str, dict] = {}  # entity_id -> {qty, cost}
    for a in db.query(InvestorAccess).filter_by(email=user.email):
        if not a.stakeholder_id:
            continue
        ct = compute_cap_table(db, a.entity_id)
        for h in ct["holders"]:
            if h["stakeholder_id"] == a.stakeholder_id:
                agg = holdings.setdefault(a.entity_id, {"qty": 0, "cost": Decimal("0")})
                agg["qty"] += h["quantity"]
                agg["cost"] += Decimal(h["amount_invested"])

    dates = set()
    for eid in holdings:
        for v in db.query(ValuationReport).filter_by(entity_id=eid, status=ValuationStatus.FINAL):
            if v.valuation_date <= today:
                dates.add(v.valuation_date)
    dates.add(today)  # always anchor the series at "now"

    def value_at(as_of) -> Decimal:
        total = Decimal("0")
        for eid, agg in holdings.items():
            fmv = current_fmv(db, eid, as_of)
            total += Decimal(agg["qty"]) * fmv if fmv is not None else agg["cost"]
        return total.quantize(CENTS, ROUND_HALF_UP)

    series = [
        {"date": d.isoformat(), "value": str(value_at(d))} for d in sorted(dates)
    ]
    return {
        "series": series,
        "current_value": series[-1]["value"] if series else "0.00",
        "holdings": len(holdings),
    }


def _grant_documents(db: Session, grant_id: str) -> list[dict]:
    """The employee's downloadable documents for a grant: the grant letter and
    any share certificates issued from exercises of it."""
    from ..models.esop import ExerciseTransaction

    docs = [
        {"id": d.id, "title": d.title, "kind": "grant_letter"}
        for d in db.query(Document).filter_by(subject_type="esop_grant", subject_id=grant_id)
    ]
    ex_ids = [e.id for e in db.query(ExerciseTransaction).filter_by(grant_id=grant_id)]
    if ex_ids:
        docs += [
            {"id": d.id, "title": d.title, "kind": "certificate"}
            for d in db.query(Document).filter(
                Document.subject_type == "esop_exercise", Document.subject_id.in_(ex_ids)
            )
        ]
    return docs


def grant_tax_estimate_for_user(
    db: Session, user: User, grant_id: str, quantity: int, marginal_rate
) -> dict | None:
    """Email-scoped 'what if I exercise N now' tax estimate for the owning
    employee. Returns None if the grant isn't theirs."""
    grant = db.get(Grant, grant_id)
    if grant is None:
        return None
    sh = db.get(Stakeholder, grant.stakeholder_id)
    if sh is None or sh.email != user.email:
        return None
    return exercise_tax_estimate(db, grant, quantity, today_ist(), marginal_rate=marginal_rate)


def grant_detail_for_user(db: Session, user: User, grant_id: str) -> dict | None:
    """One equity grant's full detail for the owning employee (matched by
    email): value summary + vesting status segments + the vesting timeline.
    Returns None if the grant isn't the user's."""
    grant = db.get(Grant, grant_id)
    if grant is None:
        return None
    sh = db.get(Stakeholder, grant.stakeholder_id)
    if sh is None or sh.email != user.email:
        return None
    today = today_ist()
    entity = db.get(LegalEntity, grant.entity_id)
    gv = grant_view(db, grant, today)
    summ = grant_value_summary(db, grant, today, gv)
    fmv = current_fmv(db, grant.entity_id, today)
    proj = vesting_projection(grant, today)
    # estimated tax on exercising everything vested now (options/RSUs)
    tax = (
        exercise_tax_estimate(db, grant, gv["exercisable"], today)
        if gv["exercisable"] > 0
        else None
    )
    return {
        "grant_id": grant.id,
        "grant_type": grant.grant_type,
        "entity_name": entity.name if entity else None,
        "tax": tax,
        "documents": _grant_documents(db, grant.id),
        "granted": gv["quantity"],
        "vested": gv["vested"],
        "exercised": gv["exercised"],
        "exercisable": gv["exercisable"],
        "unvested": gv["unvested"],
        "exercise_price": str(grant.exercise_price),
        "grant_date": grant.grant_date.isoformat(),
        "current_fmv": str(fmv) if fmv is not None else None,
        "vesting_pct": round(gv["vested"] / gv["quantity"] * 100, 2) if gv["quantity"] else 0.0,
        "full_vest_date": proj["full_vest_date"].isoformat(),
        "next_vests": [
            {"date": e["date"].isoformat(), "quantity": e["quantity"]} for e in proj["next_vests"]
        ],
        "schedule": grant_schedule(grant, today),
        **summ,
    }


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
                "updates": _updates(db, entity.id, user.email),
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
                "updates": _updates(db, entity.id, user.email),
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
    # consolidated cross-fund LP position (FR-J-18)
    lp_tot = {k: Decimal("0") for k in ("committed", "drawn", "remaining", "distributed", "nav_value")}
    lp_pending_calls = 0
    for lp in db.query(LP).filter_by(email=user.email):
        fund = db.get(Fund, lp.fund_id)
        if fund is None:
            continue
        entity = db.get(LegalEntity, fund.entity_id)
        acc = capital_accounts(db, fund)
        mine = next((x for x in acc["accounts"] if x["lp_id"] == lp.id), None)
        perf = fund_performance(db, fund)
        if mine:
            total_committed += Decimal(mine["committed"])
            for k in ("committed", "drawn", "remaining", "distributed"):
                lp_tot[k] += Decimal(mine[k])
            # LP's slice of fund NAV in the platform's unitised model
            if perf["nav_per_unit"] is not None:
                lp_tot["nav_value"] += Decimal(mine["units"]) * Decimal(perf["nav_per_unit"])

        # online capital-call notices: this LP's drawdowns with call context
        calls = {c.id: c for c in db.query(CapitalCall).filter_by(fund_id=fund.id)}
        notices = []
        for n in (
            db.query(DrawdownNotice)
            .filter_by(fund_id=fund.id, lp_id=lp.id)
            .order_by(DrawdownNotice.created_at.desc())
        ):
            call = calls.get(n.call_id)
            if not n.paid:
                lp_pending_calls += 1
            notices.append(
                {
                    "notice_id": n.id,
                    "call_no": call.call_no if call else None,
                    "purpose": call.purpose if call else None,
                    "due_date": call.due_date if call else None,
                    "amount": str(n.amount),
                    "paid": n.paid,
                    "payment_ref": n.payment_ref,
                    "acknowledged_at": n.acknowledged_at,
                    "overdue": bool(
                        not n.paid and call and call.due_date and call.due_date < today
                    ),
                }
            )
        funds.append(
            {
                "fund_id": fund.id,
                "fund_name": entity.name if entity else None,
                "sebi_category": fund.sebi_category.value,
                "account": mine,
                "capital_calls": notices,
                "look_through": lp_look_through(db, fund, lp),
                "performance": perf,
                # statements + tax forms for this LP, plus fund-wide quarterly
                # LP reports, surface here automatically
                "statements": [
                    {"id": d.id, "title": d.title, "created_at": d.created_at}
                    for d in db.query(Document)
                    .filter(
                        Document.entity_id == fund.entity_id,
                        or_(
                            and_(
                                Document.subject_type.in_(["lp_statement", "form_64c"]),
                                Document.subject_id == lp.id,
                            ),
                            and_(
                                Document.subject_type.in_(
                                    ["lp_report", "form_64d", "fund_financials", "audited_financials"]
                                ),
                                Document.subject_id == fund.id,
                            ),
                        ),
                    )
                    .order_by(Document.created_at.desc())
                ],
                # per-LP distribution history (mirrors the capital-calls list)
                "distributions": lp_distribution_history(db, fund.id, lp.id),
                # collection account the LP remits drawdowns to
                "bank": {
                    "bank_name": fund.bank_name,
                    "bank_account": fund.bank_account,
                    "bank_ifsc": fund.bank_ifsc,
                } if fund.bank_account else None,
                "updates": _updates(db, fund.entity_id, user.email),
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
                "updates": _updates(db, spv.entity_id, user.email),
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
            summ = grant_value_summary(db, g, today, gv)
            grants.append(
                {
                    "grant_id": g.id,
                    "exercise_requests": requests,
                    "entity_name": entity.name if entity else None,
                    "grant_type": g.grant_type,
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
                    "today_value": summ["today_value"],
                    "exercised_value": summ["exercised_value"],
                    "max_potential_value": summ["max_potential_value"],
                    "unit_value": summ["unit_value"],
                    "segments": summ["segments"],
                    "documents": _grant_documents(db, g.id),
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
        # consolidated LP position across every fund (FR-J-18); zeros if not an LP
        "lp_summary": {
            "funds": len(funds),
            "committed": str(lp_tot["committed"].quantize(CENTS, ROUND_HALF_UP)),
            "drawn": str(lp_tot["drawn"].quantize(CENTS, ROUND_HALF_UP)),
            "remaining": str(lp_tot["remaining"].quantize(CENTS, ROUND_HALF_UP)),
            "distributed": str(lp_tot["distributed"].quantize(CENTS, ROUND_HALF_UP)),
            "nav_value": str(lp_tot["nav_value"].quantize(CENTS, ROUND_HALF_UP)),
            "pending_calls": lp_pending_calls,
        },
        "companies": companies,
        "funds": funds,
        "spvs": spvs,
        "equity_grants": grants,
        "liquidity_events": _liquidity_for_user(db, user, today),
        # KPI requests addressed to this user as a portfolio-company contact
        "kpi_requests": kpi_requests_for_user(db, user),
    }


def acknowledge_notice(db: Session, user: User, notice_id: str) -> dict:
    """LP self-service: acknowledge a capital-call notice from the portal.
    Scoped by LP email match; idempotent (re-acknowledging keeps the first
    timestamp)."""
    notice = db.get(DrawdownNotice, notice_id)
    lp = db.get(LP, notice.lp_id) if notice else None
    if notice is None or lp is None or lp.email != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Notice not found")
    if notice.acknowledged_at is None:
        notice.acknowledged_at = now_ist()
        db.commit()
    return {"notice_id": notice.id, "acknowledged_at": notice.acknowledged_at}


def kpi_requests_for_user(db: Session, user: User) -> list[dict]:
    """Open KPI requests addressed to this user's email (investee self-service)."""
    from ..models.fund import KPIRequest, KPIRequestStatus, PortfolioInvestment

    out = []
    for r in (
        db.query(KPIRequest)
        .filter_by(contact_email=user.email)
        .filter(KPIRequest.status != KPIRequestStatus.ACCEPTED)
        .order_by(KPIRequest.created_at.desc())
    ):
        inv = db.get(PortfolioInvestment, r.investment_id)
        fund = db.get(Fund, r.fund_id)
        entity = db.get(LegalEntity, fund.entity_id) if fund else None
        out.append(
            {
                "id": r.id,
                "fund_name": entity.name if entity else None,
                "company_name": inv.company_name if inv else None,
                "period_label": r.period_label,
                "as_of": r.as_of,
                "due_date": r.due_date,
                "status": r.status.value,
                "overdue": bool(
                    r.status == KPIRequestStatus.PENDING
                    and r.due_date
                    and r.due_date < today_ist()
                ),
            }
        )
    return out


def submit_kpi_request(db: Session, user: User, request_id: str, payload: dict) -> dict:
    """The company's reporting contact submits KPI values from their portal.
    Email-scoped; only a pending request can be submitted."""
    from ..models.fund import KPIRequest
    from .fund import submit_request_values

    req = db.get(KPIRequest, request_id)
    if req is None or req.contact_email != user.email:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "KPI request not found")
    return submit_request_values(db, req, payload)

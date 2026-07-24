"""Portfolio-company monitoring: KPIs, custom KPI definitions, internal
benchmarking, metric alert rules, SEBI independent valuation, company notes,
KPI reporting requests & schedules, the web-native LP report view, and
rules-based portfolio signals."""
import datetime
import secrets
from decimal import Decimal
from statistics import median, quantiles

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...clock import now_ist, today_ist
from ...models.fund import (
    CompanyNote,
    Fund,
    KPIDefinition,
    KPIRequest,
    KPIRequestSchedule,
    KPIRequestStatus,
    MetricAlertRule,
    PortfolioInvestment,
    PortfolioKPI,
    PortfolioValuation,
)
from ..money import q
from .profile import capital_accounts, period_activity, schedule_of_investments

# --- portfolio-company monitoring (Carta "portfolio monitoring") -------------
LOW_RUNWAY_MONTHS = 6  # flag threshold


def _runway_months(cash: Decimal | None, burn: Decimal | None) -> float | None:
    if cash is None or burn is None or burn <= 0:
        return None
    return round(float(cash / burn), 1)


def add_kpi(db: Session, investment: PortfolioInvestment, data: dict) -> PortfolioKPI:
    # custom metric values are kept only for keys the fund has defined (FR-J-23)
    custom = data.pop("custom", None)
    if custom:
        defined = {
            d.key for d in db.query(KPIDefinition).filter_by(fund_id=investment.fund_id)
        }
        custom = {
            k: str(Decimal(str(v)))
            for k, v in custom.items()
            if k in defined and v is not None
        }
    kpi = PortfolioKPI(
        investment_id=investment.id,
        fund_id=investment.fund_id,
        custom=custom or None,
        **data,
    )
    db.add(kpi)
    db.commit()
    db.refresh(kpi)
    return kpi


def _kpi_view(k: PortfolioKPI) -> dict:
    return {
        "id": k.id,
        "period_label": k.period_label,
        "as_of": k.as_of,
        "revenue": str(q(k.revenue)) if k.revenue is not None else None,
        "cash": str(q(k.cash)) if k.cash is not None else None,
        "monthly_burn": str(q(k.monthly_burn)) if k.monthly_burn is not None else None,
        "headcount": k.headcount,
        "runway_months": _runway_months(k.cash, k.monthly_burn),
        "note": k.note,
        "custom": k.custom or {},
    }


def kpi_history(db: Session, investment: PortfolioInvestment) -> list[dict]:
    rows = (
        db.query(PortfolioKPI)
        .filter_by(investment_id=investment.id)
        .order_by(PortfolioKPI.as_of)
        .all()
    )
    return [_kpi_view(k) for k in rows]


def portfolio_monitoring(db: Session, fund: Fund) -> dict:
    """Latest reported KPIs per portfolio company + period-over-period revenue
    growth, runway and low-runway flag, with portfolio-level roll-ups."""
    companies = []
    tot_revenue = Decimal("0")
    tot_cash = Decimal("0")
    low_runway = 0
    reporting = 0

    for inv in db.query(PortfolioInvestment).filter_by(fund_id=fund.id):
        rows = (
            db.query(PortfolioKPI)
            .filter_by(investment_id=inv.id)
            .order_by(PortfolioKPI.as_of.desc())
            .all()
        )
        latest = rows[0] if rows else None
        prev = rows[1] if len(rows) > 1 else None

        growth = None
        if latest and prev and latest.revenue is not None and prev.revenue and Decimal(prev.revenue) != 0:
            growth = round(
                float((Decimal(latest.revenue) - Decimal(prev.revenue)) / Decimal(prev.revenue) * 100), 1
            )
        runway = _runway_months(latest.cash, latest.monthly_burn) if latest else None

        if latest:
            reporting += 1
            if latest.revenue is not None:
                tot_revenue += Decimal(latest.revenue)
            if latest.cash is not None:
                tot_cash += Decimal(latest.cash)
            if runway is not None and runway < LOW_RUNWAY_MONTHS:
                low_runway += 1

        companies.append({
            "investment_id": inv.id,
            "company_name": inv.company_name,
            "sector": inv.sector,
            "contact_email": inv.contact_email,
            "ownership_pct": str(inv.ownership_pct),
            "periods": len(rows),
            "latest": _kpi_view(latest) if latest else None,
            "revenue_growth_pct": growth,
            "runway_months": runway,
            "low_runway": runway is not None and runway < LOW_RUNWAY_MONTHS,
            "revenue_series": [
                {"x": k.as_of.isoformat(), "y": float(k.revenue)}
                for k in sorted(rows, key=lambda r: r.as_of)
                if k.revenue is not None
            ],
        })

    return {
        "fund_id": fund.id,
        "totals": {
            "companies": db.query(PortfolioInvestment).filter_by(fund_id=fund.id).count(),
            "reporting": reporting,
            "latest_revenue": str(q(tot_revenue)),
            "cash": str(q(tot_cash)),
            "low_runway": low_runway,
        },
        "companies": companies,
    }


# --- custom KPI definitions + ESG presets (FR-J-23) ---------------------------
KPI_UNITS = ("inr", "number", "pct")

ESG_KPI_PRESETS = [
    {"key": "female_headcount_pct", "label": "Female headcount %", "unit": "pct"},
    {"key": "independent_directors_pct", "label": "Independent directors %", "unit": "pct"},
    {"key": "ghg_emissions_tco2e", "label": "GHG emissions (tCO2e)", "unit": "number"},
    {"key": "energy_use_kwh", "label": "Energy use (kWh)", "unit": "number"},
    {"key": "csr_spend", "label": "CSR spend", "unit": "inr"},
]


def _kpi_key(label: str) -> str:
    out: list[str] = []
    for ch in label.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "_":
            out.append("_")
    return "".join(out).strip("_")[:64]


def _definition_view(d: KPIDefinition) -> dict:
    return {"id": d.id, "key": d.key, "label": d.label, "unit": d.unit}


def list_kpi_definitions(db: Session, fund: Fund) -> list[dict]:
    rows = (
        db.query(KPIDefinition)
        .filter_by(fund_id=fund.id)
        .order_by(KPIDefinition.created_at)
        .all()
    )
    return [_definition_view(d) for d in rows]


def create_kpi_definition(
    db: Session, fund: Fund, data: dict, user_id: str
) -> KPIDefinition:
    unit = data.get("unit") or "number"
    if unit not in KPI_UNITS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unit must be one of {KPI_UNITS}")
    key = _kpi_key(data.get("key") or data["label"])
    if not key:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "label must contain letters or digits")
    if db.query(KPIDefinition).filter_by(fund_id=fund.id, key=key).first():
        raise HTTPException(status.HTTP_409_CONFLICT, f"metric '{key}' is already defined")
    d = KPIDefinition(
        fund_id=fund.id, key=key, label=data["label"].strip(), unit=unit, created_by=user_id
    )
    db.add(d)
    db.commit()
    db.refresh(d)
    return d


def delete_kpi_definition(db: Session, fund: Fund, definition_id: str) -> None:
    d = db.get(KPIDefinition, definition_id)
    if d is None or d.fund_id != fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Metric definition not found")
    # drop any alert rules that reference this custom metric — otherwise they
    # linger in the catalog as no-ops (metric no longer resolvable in signals)
    for r in db.query(MetricAlertRule).filter_by(
        fund_id=fund.id, metric=f"custom.{d.key}"
    ):
        db.delete(r)
    # historical values stay in PortfolioKPI.custom; they just stop being shown
    db.delete(d)
    db.commit()


# --- internal benchmarking: portfolio medians (FR-J-24) -----------------------
CORE_METRICS = [
    {"key": "revenue", "label": "Revenue", "unit": "inr"},
    {"key": "revenue_growth_pct", "label": "Revenue growth %", "unit": "pct"},
    {"key": "monthly_burn", "label": "Monthly burn", "unit": "inr"},
    {"key": "runway_months", "label": "Runway (months)", "unit": "number"},
    {"key": "headcount", "label": "Headcount", "unit": "number"},
]


def metric_options(db: Session, fund: Fund) -> list[dict]:
    """The comparable metric catalog: core KPIs + the fund's custom
    definitions (keyed `custom.<key>`). Shared by benchmarks and alerts."""
    return CORE_METRICS + [
        {"key": f"custom.{d['key']}", "label": d["label"], "unit": d["unit"]}
        for d in list_kpi_definitions(db, fund)
    ]


def portfolio_benchmarks(db: Session, fund: Fund) -> dict:
    """Companies side-by-side on the core and custom metrics from each one's
    latest reported period, against the portfolio median. Pure derivation."""
    defs = list_kpi_definitions(db, fund)
    metrics = metric_options(db, fund)

    rows = []
    for c in portfolio_monitoring(db, fund)["companies"]:
        latest = c["latest"] or {}
        values: dict[str, float | None] = {
            "revenue": float(latest["revenue"]) if latest.get("revenue") else None,
            "revenue_growth_pct": c["revenue_growth_pct"],
            "monthly_burn": float(latest["monthly_burn"]) if latest.get("monthly_burn") else None,
            "runway_months": c["runway_months"],
            "headcount": latest.get("headcount"),
        }
        for d in defs:
            v = (latest.get("custom") or {}).get(d["key"])
            values[f"custom.{d['key']}"] = float(v) if v is not None else None
        rows.append(
            {
                "investment_id": c["investment_id"],
                "company_name": c["company_name"],
                "sector": c["sector"],
                "values": values,
            }
        )

    def _medians(over: list[dict]) -> dict:
        out = {}
        for m in metrics:
            xs = [r["values"][m["key"]] for r in over if r["values"][m["key"]] is not None]
            out[m["key"]] = round(median(xs), 2) if xs else None
        return out

    # segment comparison: medians per sector tag (untagged companies grouped as "—")
    by_segment: dict[str, list[dict]] = {}
    for r in rows:
        by_segment.setdefault(r["sector"] or "—", []).append(r)
    segments = [
        {"segment": seg, "companies": len(members), "medians": _medians(members)}
        for seg, members in sorted(by_segment.items())
    ]

    # distribution stats per metric (Visible-style quartile view)
    stats = {}
    for m in metrics:
        xs = sorted(r["values"][m["key"]] for r in rows if r["values"][m["key"]] is not None)
        if not xs:
            stats[m["key"]] = None
            continue
        q1, q2, q3 = (
            [round(q, 2) for q in quantiles(xs, n=4, method="inclusive")]
            if len(xs) >= 2
            else [xs[0], xs[0], xs[0]]
        )
        stats[m["key"]] = {
            "min": round(xs[0], 2),
            "q1": q1,
            "median": q2,
            "q3": q3,
            "max": round(xs[-1], 2),
            "total": round(sum(xs), 2),
            "avg": round(sum(xs) / len(xs), 2),
            "reporters": len(xs),
        }

    return {
        "fund_id": fund.id,
        "metrics": metrics,
        "rows": rows,
        "medians": _medians(rows),
        "segments": segments if len(segments) > 1 else [],
        "stats": stats,
    }


# --- metric alert rules (Visible-style thresholds) -----------------------------
ALERT_COMPARATORS = ("lt", "gt")
ALERT_SEVERITIES = ("high", "warn")


def _rule_view(r: MetricAlertRule) -> dict:
    return {
        "id": r.id,
        "metric": r.metric,
        "comparator": r.comparator,
        "threshold": str(r.threshold),
        "severity": r.severity,
    }


def list_alert_rules(db: Session, fund: Fund) -> dict:
    rows = (
        db.query(MetricAlertRule)
        .filter_by(fund_id=fund.id)
        .order_by(MetricAlertRule.created_at)
        .all()
    )
    return {"rules": [_rule_view(r) for r in rows], "metrics": metric_options(db, fund)}


def create_alert_rule(db: Session, fund: Fund, data: dict, user_id: str) -> dict:
    if data["comparator"] not in ALERT_COMPARATORS:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"comparator must be one of {ALERT_COMPARATORS}")
    if data.get("severity", "warn") not in ALERT_SEVERITIES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"severity must be one of {ALERT_SEVERITIES}")
    known = {m["key"] for m in metric_options(db, fund)}
    if data["metric"] not in known:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown metric '{data['metric']}'")
    r = MetricAlertRule(
        fund_id=fund.id,
        metric=data["metric"],
        comparator=data["comparator"],
        threshold=Decimal(str(data["threshold"])),
        severity=data.get("severity", "warn"),
        created_by=user_id,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return _rule_view(r)


def delete_alert_rule(db: Session, fund: Fund, rule_id: str) -> None:
    r = db.get(MetricAlertRule, rule_id)
    if r is None or r.fund_id != fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Alert rule not found")
    db.delete(r)
    db.commit()


def _fmt_metric(value: float | Decimal, unit: str) -> str:
    if unit == "inr":
        return _inr(value)
    if unit == "pct":
        return f"{round(float(value), 1)}%"
    return f"{round(float(value), 1):g}"


# --- internal team notes on portfolio companies ---------------------------------
def _note_view(n: CompanyNote, author: str | None) -> dict:
    return {
        "id": n.id,
        "body": n.body,
        "author": author,
        "created_at": n.created_at,
    }


def add_company_note(
    db: Session, investment: PortfolioInvestment, body: str, user_id: str
) -> dict:
    from ...models.identity import User

    n = CompanyNote(
        investment_id=investment.id,
        fund_id=investment.fund_id,
        body=body.strip(),
        created_by=user_id,
    )
    db.add(n)
    db.commit()
    db.refresh(n)
    u = db.get(User, user_id)
    return _note_view(n, u.full_name if u else None)


def list_company_notes(db: Session, investment: PortfolioInvestment) -> list[dict]:
    from ...models.identity import User

    rows = (
        db.query(CompanyNote)
        .filter_by(investment_id=investment.id)
        .order_by(CompanyNote.created_at.desc())
        .all()
    )
    authors = {u.id: u.full_name for u in db.query(User).filter(User.id.in_([n.created_by for n in rows]))} if rows else {}
    return [_note_view(n, authors.get(n.created_by)) for n in rows]


def delete_company_note(db: Session, investment: PortfolioInvestment, note_id: str) -> None:
    n = db.get(CompanyNote, note_id)
    if n is None or n.investment_id != investment.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Note not found")
    db.delete(n)
    db.commit()


# --- SEBI independent portfolio valuation (FR-J-15) --------------------------
VALUATION_METHODOLOGIES = {
    "ipev_market": "IPEV — market multiples",
    "ipev_recent_txn": "IPEV — recent transaction price",
    "dcf": "Discounted cash flow",
    "nav": "Net assets / book value",
    "cost": "Cost (no observable change)",
}


def set_valuation_policy(db: Session, fund: Fund, valuer_name, frequency_months) -> Fund:
    fund.valuer_name = valuer_name
    fund.valuation_frequency_months = frequency_months
    db.commit()
    db.refresh(fund)
    return fund


def record_valuation(db: Session, investment: PortfolioInvestment, data: dict) -> PortfolioValuation:
    """Append a valuation and roll it into the holding's mark (latest by as_of)."""
    val = PortfolioValuation(investment_id=investment.id, fund_id=investment.fund_id, **data)
    db.add(val)
    db.flush()
    # keep the holding's mark = latest valuation by as_of
    latest = (
        db.query(PortfolioValuation)
        .filter_by(investment_id=investment.id)
        .order_by(PortfolioValuation.as_of.desc(), PortfolioValuation.created_at.desc())
        .first()
    )
    investment.current_value = latest.value
    investment.marked_on = latest.as_of
    db.commit()
    db.refresh(val)
    return val


def _valuation_view(v: PortfolioValuation) -> dict:
    return {
        "id": v.id,
        "as_of": v.as_of,
        "value": str(q(v.value)),
        "methodology": v.methodology,
        "methodology_label": VALUATION_METHODOLOGIES.get(v.methodology, v.methodology),
        "valuer": v.valuer,
        "is_independent": v.is_independent,
        "note": v.note,
    }


def valuation_history(db: Session, investment: PortfolioInvestment) -> list[dict]:
    rows = (
        db.query(PortfolioValuation)
        .filter_by(investment_id=investment.id)
        .order_by(PortfolioValuation.as_of.desc())
        .all()
    )
    return [_valuation_view(v) for v in rows]


def valuation_summary(db: Session, fund: Fund) -> dict:
    """Per-holding latest valuation + staleness vs the fund's valuation policy,
    with SEBI-oriented roll-ups (valued / stale / independent counts)."""
    freq = fund.valuation_frequency_months or 12
    today = today_ist()
    stale_before = today - datetime.timedelta(days=int(freq * 30.4))

    holdings = []
    valued = stale = independent = 0
    for inv in db.query(PortfolioInvestment).filter_by(fund_id=fund.id):
        latest = (
            db.query(PortfolioValuation)
            .filter_by(investment_id=inv.id)
            .order_by(PortfolioValuation.as_of.desc(), PortfolioValuation.created_at.desc())
            .first()
        )
        count = db.query(PortfolioValuation).filter_by(investment_id=inv.id).count()
        is_stale = latest is None or latest.as_of < stale_before
        if latest is not None:
            valued += 1
            if latest.is_independent:
                independent += 1
        if is_stale:
            stale += 1
        holdings.append({
            "investment_id": inv.id,
            "company_name": inv.company_name,
            "cost": str(q(inv.amount)),
            "valuations": count,
            "latest": _valuation_view(latest) if latest else None,
            "stale": is_stale,
        })

    return {
        "fund_id": fund.id,
        "policy": {
            "valuer_name": fund.valuer_name,
            "frequency_months": freq,
        },
        "methodologies": VALUATION_METHODOLOGIES,
        "totals": {
            "holdings": len(holdings),
            "valued": valued,
            "stale": stale,
            "independent": independent,
        },
        "holdings": holdings,
    }


# --- KPI reporting requests (investee self-service, Vestberry-style) ----------
def create_kpi_request(
    db: Session, investment: PortfolioInvestment, data: dict, user_id: str
) -> KPIRequest:
    """Ask the company's reporting contact for one period of KPIs. Keeps the
    investment's contact_email in sync and notifies the contact if they have a
    Paper account (the request also appears in their portal either way)."""
    from ...models.identity import User
    from ..notification import notify

    investment.contact_email = data["contact_email"]
    req = KPIRequest(
        investment_id=investment.id,
        fund_id=investment.fund_id,
        created_by=user_id,
        token=secrets.token_urlsafe(16),
        **data,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    contact = db.query(User).filter_by(email=req.contact_email).first()
    if contact:
        notify(
            db,
            contact.id,
            "kpi_request",
            f"KPI request: {investment.company_name} — {req.period_label}",
            f"Report revenue, cash, burn and headcount{f' by {req.due_date}' if req.due_date else ''} from your portal.",
        )
    return req


def _kpi_request_view(r: KPIRequest, company_name: str | None = None) -> dict:
    return {
        "id": r.id,
        "investment_id": r.investment_id,
        "company_name": company_name,
        "period_label": r.period_label,
        "as_of": r.as_of,
        "due_date": r.due_date,
        "contact_email": r.contact_email,
        "status": r.status.value,
        "overdue": bool(
            r.status == KPIRequestStatus.PENDING and r.due_date and r.due_date < today_ist()
        ),
        "revenue": str(q(r.revenue)) if r.revenue is not None else None,
        "cash": str(q(r.cash)) if r.cash is not None else None,
        "monthly_burn": str(q(r.monthly_burn)) if r.monthly_burn is not None else None,
        "headcount": r.headcount,
        "note": r.note,
        "submitted_at": r.submitted_at,
        "kpi_id": r.kpi_id,
        "token": r.token,
    }


def submit_request_values(db: Session, req: KPIRequest, payload: dict) -> dict:
    """Write submitted KPI values onto a pending request (shared by the portal
    and the no-login token link)."""
    if req.status != KPIRequestStatus.PENDING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Request already submitted")
    for k, v in payload.items():
        setattr(req, k, v)
    req.status = KPIRequestStatus.SUBMITTED
    req.submitted_at = now_ist()
    db.commit()
    return {"id": req.id, "status": req.status.value, "submitted_at": req.submitted_at}


# --- recurring request schedules (Visible-style scheduled Requests) ------------
SCHEDULE_GRACE_DAYS = 14  # due date = period end + grace


def _last_completed_period(today: datetime.date, cadence: str) -> tuple[str, datetime.date]:
    """Label + end date of the last fully completed month / calendar quarter
    (quarters labelled as Indian-FY quarters, e.g. Apr–Jun 2026 -> FY27 Q1)."""
    if cadence == "monthly":
        end = today.replace(day=1) - datetime.timedelta(days=1)
        return end.strftime("%b %Y"), end
    qstart_month = ((today.month - 1) // 3) * 3 + 1
    end = datetime.date(today.year, qstart_month, 1) - datetime.timedelta(days=1)
    fy = end.year + 1 if end.month >= 4 else end.year
    qn = (end.month - 1) // 3 if end.month >= 4 else 4
    return f"FY{fy % 100} Q{qn}", end


def ensure_scheduled_requests(db: Session, fund: Fund) -> int:
    """Materialise the KPI request for each schedule's last completed period
    if it doesn't exist yet (on-read, idempotent). Returns how many were created."""
    created = 0
    today = today_ist()
    for s in db.query(KPIRequestSchedule).filter_by(fund_id=fund.id).all():
        inv = db.get(PortfolioInvestment, s.investment_id)
        if inv is None or not inv.contact_email:
            continue
        label, end = _last_completed_period(today, s.cadence)
        if db.query(KPIRequest).filter_by(investment_id=inv.id, period_label=label).first():
            continue
        create_kpi_request(
            db,
            inv,
            {
                "period_label": label,
                "as_of": end,
                "due_date": end + datetime.timedelta(days=SCHEDULE_GRACE_DAYS),
                "contact_email": inv.contact_email,
            },
            s.created_by,
        )
        created += 1
    return created


def _schedule_view(s: KPIRequestSchedule, inv: PortfolioInvestment | None) -> dict:
    return {
        "id": s.id,
        "investment_id": s.investment_id,
        "company_name": inv.company_name if inv else None,
        "contact_email": inv.contact_email if inv else None,
        "cadence": s.cadence,
    }


def list_kpi_schedules(db: Session, fund: Fund) -> list[dict]:
    return [
        _schedule_view(s, db.get(PortfolioInvestment, s.investment_id))
        for s in db.query(KPIRequestSchedule)
        .filter_by(fund_id=fund.id)
        .order_by(KPIRequestSchedule.created_at)
    ]


def upsert_kpi_schedule(
    db: Session, investment: PortfolioInvestment, data: dict, user_id: str
) -> dict:
    if data.get("contact_email"):
        investment.contact_email = data["contact_email"]
    if not investment.contact_email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Set a reporting contact for the company first"
        )
    s = db.query(KPIRequestSchedule).filter_by(investment_id=investment.id).first()
    if s is None:
        s = KPIRequestSchedule(
            investment_id=investment.id,
            fund_id=investment.fund_id,
            cadence=data["cadence"],
            created_by=user_id,
        )
        db.add(s)
    else:
        s.cadence = data["cadence"]
    db.commit()
    db.refresh(s)
    return _schedule_view(s, investment)


def delete_kpi_schedule(db: Session, fund: Fund, investment_id: str) -> None:
    s = (
        db.query(KPIRequestSchedule)
        .filter_by(fund_id=fund.id, investment_id=investment_id)
        .first()
    )
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Schedule not found")
    db.delete(s)
    db.commit()


def list_kpi_requests(db: Session, fund: Fund) -> list[dict]:
    names = {
        i.id: i.company_name
        for i in db.query(PortfolioInvestment).filter_by(fund_id=fund.id)
    }
    return [
        _kpi_request_view(r, names.get(r.investment_id))
        for r in db.query(KPIRequest)
        .filter_by(fund_id=fund.id)
        .order_by(KPIRequest.created_at.desc())
    ]


def accept_kpi_request(db: Session, req: KPIRequest) -> PortfolioKPI:
    """GP accepts a submitted request — the values become a PortfolioKPI period."""
    if req.status != KPIRequestStatus.SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Request has not been submitted")
    inv = db.get(PortfolioInvestment, req.investment_id)
    kpi = add_kpi(
        db,
        inv,
        {
            "period_label": req.period_label,
            "as_of": req.as_of,
            "revenue": req.revenue,
            "cash": req.cash,
            "monthly_burn": req.monthly_burn,
            "headcount": req.headcount,
            "note": req.note,
        },
    )
    req.kpi_id = kpi.id
    req.status = KPIRequestStatus.ACCEPTED
    db.commit()
    return kpi


def reopen_kpi_request(db: Session, req: KPIRequest) -> KPIRequest:
    """Send a submitted request back for resubmission (values look wrong)."""
    if req.status != KPIRequestStatus.SUBMITTED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Only a submitted request can be reopened")
    req.status = KPIRequestStatus.PENDING
    req.submitted_at = None
    db.commit()
    db.refresh(req)
    return req


# --- web-native LP report view (Rundit-style magazine page) --------------------
def default_report_period(today: datetime.date) -> tuple[str, datetime.date, datetime.date]:
    """Label + start/end of the last completed calendar quarter (Indian-FY label)."""
    label, end = _last_completed_period(today, "quarterly")
    start = datetime.date(end.year, end.month - 2, 1)
    return label, start, end


def lp_report_data(
    db: Session,
    fund: Fund,
    fund_name: str,
    period_label: str,
    start: datetime.date,
    end: datetime.date,
) -> dict:
    """The quarterly LP report as structured data for the on-screen magazine
    view — same sources as the generated document (FR-J-22)."""
    from ..fund_perf import fund_performance

    caps = capital_accounts(db, fund)["totals"]
    perf = fund_performance(db, fund)
    activity = period_activity(db, fund, start, end)
    soi = schedule_of_investments(db, fund)
    vals = valuation_summary(db, fund)["totals"]
    today = today_ist()

    holdings = []
    for h in soi["holdings"]:
        cost = Decimal(h["cost"])
        gain_pct = (
            round(float(Decimal(h["unrealized_gain"]) / cost * 100), 1) if cost > 0 else None
        )
        holding_years = None
        if h["invested_on"]:
            invested = datetime.date.fromisoformat(str(h["invested_on"]))
            holding_years = round((today - invested).days / 365, 1)
        holdings.append({**h, "gain_pct": gain_pct, "holding_years": holding_years})

    return {
        "fund_id": fund.id,
        "fund_name": fund_name,
        "category": fund.sebi_category.value,
        "period_label": period_label,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "prepared_on": today.isoformat(),
        "snapshot": caps,
        "performance": {
            "nav": perf["nav"],
            "nav_per_unit": perf["nav_per_unit"],
            "dpi": perf["dpi"],
            "rvpi": perf["rvpi"],
            "tvpi": perf["tvpi"],
            "xirr_pct": perf["xirr_pct"],
        },
        "activity": activity,
        "holdings": holdings,
        "totals": soi["totals"],
        "valuation_status": vals,
    }


# --- portfolio signals (Vestberry-style risk early-warning) -------------------
REVENUE_DECLINE_HIGH_PCT = 20   # QoQ drop beyond this is high severity
SILENT_REPORTING_DAYS = 183     # ~6 months without a reported period
FOLLOW_ON_RUNWAY_MONTHS = 12    # healthy runway threshold for follow-on


def _inr(value) -> str:
    """₹ with Indian lakh/crore digit grouping (12,34,56,789) for signal text."""
    n = int(Decimal(value))
    sign = "-" if n < 0 else ""
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        s = ",".join(groups + [tail])
    return f"₹{sign}{s}"


def portfolio_signals(db: Session, fund: Fund) -> dict:
    """Rules-based signals over the KPI history and marks — which companies
    need attention (declining revenue, short runway, impaired marks, gone
    silent) and which look ready for follow-on capital. Pure derivation."""
    today = today_ist()
    companies = []
    totals = {"high": 0, "warn": 0, "info": 0, "positive": 0}
    alert_rules = db.query(MetricAlertRule).filter_by(fund_id=fund.id).all()
    metric_meta = {m["key"]: m for m in metric_options(db, fund)} if alert_rules else {}

    for inv in db.query(PortfolioInvestment).filter_by(fund_id=fund.id):
        rows = (
            db.query(PortfolioKPI)
            .filter_by(investment_id=inv.id)
            .order_by(PortfolioKPI.as_of.desc())
            .all()
        )
        latest = rows[0] if rows else None
        prev = rows[1] if len(rows) > 1 else None
        signals: list[dict] = []

        def add(kind: str, severity: str, message: str) -> None:
            signals.append({"kind": kind, "severity": severity, "message": message})
            totals[severity] += 1

        # revenue decline, period over period
        growth = None
        if latest and prev and latest.revenue is not None and prev.revenue:
            change = Decimal(latest.revenue) - Decimal(prev.revenue)
            growth = float(change / Decimal(prev.revenue) * 100)
            if change < 0:
                drop = abs(round(growth, 1))
                add(
                    "revenue_decline",
                    "high" if drop > REVENUE_DECLINE_HIGH_PCT else "warn",
                    f"Revenue down {drop}% vs {prev.period_label} "
                    f"({_inr(prev.revenue)} → {_inr(latest.revenue)})",
                )

        # runway from the latest period
        runway = _runway_months(latest.cash, latest.monthly_burn) if latest else None
        if runway is not None and runway < LOW_RUNWAY_MONTHS:
            add("low_runway", "high", f"Runway {runway} months — under {LOW_RUNWAY_MONTHS}")

        # mark below cost (impairment)
        if inv.current_value is not None and Decimal(inv.current_value) < Decimal(inv.amount):
            pct = round(
                float((Decimal(inv.amount) - Decimal(inv.current_value)) / Decimal(inv.amount) * 100), 1
            )
            add(
                "mark_below_cost",
                "warn",
                f"Marked {pct}% below cost ({_inr(inv.amount)} → {_inr(inv.current_value)})",
            )

        # reporting cadence
        if latest is None:
            add("never_reported", "info", "No KPI periods reported yet — request KPIs")
        elif (today - latest.as_of).days > SILENT_REPORTING_DAYS:
            add(
                "reporting_silent",
                "warn",
                f"No report since {latest.period_label} ({latest.as_of}) — over 6 months",
            )

        # fund-defined metric alerts against the latest period
        if alert_rules:
            values: dict[str, float | None] = {
                "revenue": float(latest.revenue) if latest and latest.revenue is not None else None,
                "revenue_growth_pct": growth,
                "monthly_burn": float(latest.monthly_burn) if latest and latest.monthly_burn is not None else None,
                "runway_months": runway,
                "headcount": latest.headcount if latest else None,
            }
            for k, v in ((latest.custom or {}).items() if latest else ()):
                if v is not None:
                    values[f"custom.{k}"] = float(v)
            for r in alert_rules:
                v = values.get(r.metric)
                meta = metric_meta.get(r.metric)
                if v is None or meta is None:
                    continue
                threshold = float(r.threshold)
                if (r.comparator == "lt" and v < threshold) or (r.comparator == "gt" and v > threshold):
                    word = "below" if r.comparator == "lt" else "above"
                    add(
                        "metric_alert",
                        r.severity,
                        f"{meta['label']} {_fmt_metric(v, meta['unit'])} — {word} the "
                        f"{_fmt_metric(threshold, meta['unit'])} alert threshold",
                    )

        # the positive signal: growing and well-funded
        if (
            growth is not None
            and growth > 0
            and runway is not None
            and runway >= FOLLOW_ON_RUNWAY_MONTHS
        ):
            add(
                "follow_on_candidate",
                "positive",
                f"Growing {round(growth, 1)}% with {runway} months runway — follow-on candidate",
            )

        if signals:
            companies.append({
                "investment_id": inv.id,
                "company_name": inv.company_name,
                "signals": signals,
            })

    total_companies = db.query(PortfolioInvestment).filter_by(fund_id=fund.id).count()
    return {
        "fund_id": fund.id,
        "totals": {**totals, "clear": total_companies - len(companies)},
        "companies": companies,
    }

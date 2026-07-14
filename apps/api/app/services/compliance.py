"""Compliance calendar service (FR-H): generate statutory obligations from
entity facts (FY end) using the rules registry, and surface overdue status."""
import datetime

from sqlalchemy.orm import Session

from ..compliance.rules import RULES, due_date_for
from ..models.compliance import ComplianceObligation, ObligationStatus

_OPEN = {ObligationStatus.DUE, ObligationStatus.IN_PREP}


def generate_for_fy(db: Session, entity_id: str, fy_end: datetime.date) -> int:
    """Create obligations for the financial year ending `fy_end`. Idempotent:
    skips obligations that already exist for the same form + period."""
    period = f"FY{fy_end.year}"
    created = 0
    for rule in RULES:
        exists = (
            db.query(ComplianceObligation)
            .filter_by(entity_id=entity_id, form_code=rule.form_code, period_label=period)
            .first()
        )
        if exists:
            continue
        db.add(
            ComplianceObligation(
                entity_id=entity_id,
                form_code=rule.form_code,
                title=rule.title,
                category=rule.category,
                period_label=period,
                due_date=due_date_for(rule, fy_end),
                status=ObligationStatus.DUE,
            )
        )
        created += 1
    db.commit()
    return created


def add_obligation(
    db: Session,
    entity_id: str,
    *,
    form_code: str,
    title: str,
    category: str,
    due_date: datetime.date,
    period_label: str,
) -> ComplianceObligation | None:
    """Idempotently add a single obligation (used by event-based filings).
    Does not commit — the caller's transaction does."""
    exists = (
        db.query(ComplianceObligation)
        .filter_by(entity_id=entity_id, form_code=form_code, period_label=period_label)
        .first()
    )
    if exists:
        return exists
    ob = ComplianceObligation(
        entity_id=entity_id,
        form_code=form_code,
        title=title,
        category=category,
        period_label=period_label,
        due_date=due_date,
        status=ObligationStatus.DUE,
    )
    db.add(ob)
    db.flush()
    return ob


def _next_month_day(period: datetime.date, day: int) -> datetime.date:
    m, y = (1, period.year + 1) if period.month == 12 else (period.month + 1, period.year)
    return datetime.date(y, m, day)


def generate_periodic(db: Session, entity_id: str, fy_end: datetime.date) -> int:
    """Generate recurring GST (monthly GSTR-3B) and TDS (quarterly 26Q) for the
    financial year ending `fy_end` (assumes an Apr–Mar FY). Idempotent."""
    start_year = fy_end.year - 1
    # 12 monthly GSTR-3B, due 20th of the following month
    for i in range(12):
        month = 4 + i
        year = start_year if month <= 12 else start_year + 1
        m = month if month <= 12 else month - 12
        period = datetime.date(year, m, 1)
        add_obligation(
            db,
            entity_id,
            form_code="GSTR-3B",
            title="GST monthly return (GSTR-3B)",
            category="GST",
            due_date=_next_month_day(period, 20),
            period_label=period.strftime("%b-%Y"),
        )
    # 4 quarterly TDS (26Q)
    quarters = [
        ("Q1", datetime.date(start_year, 7, 31)),
        ("Q2", datetime.date(start_year, 10, 31)),
        ("Q3", datetime.date(fy_end.year, 1, 31)),
        ("Q4", datetime.date(fy_end.year, 5, 31)),
    ]
    for label, due in quarters:
        add_obligation(
            db,
            entity_id,
            form_code="TDS 26Q",
            title="TDS return (Form 26Q)",
            category="TAX",
            due_date=due,
            period_label=f"{label} FY{fy_end.year}",
        )
    db.commit()
    # report how many periodic obligations now exist for this entity
    return (
        db.query(ComplianceObligation)
        .filter_by(entity_id=entity_id)
        .filter(ComplianceObligation.form_code.in_(["GSTR-3B", "TDS 26Q"]))
        .count()
    )


def generate_aif(db: Session, entity_id: str, fy_end: datetime.date) -> int:
    """SEBI AIF calendar for a fund entity (FR-J-8): quarterly activity reports
    (due 15 days after quarter end), the annual PPM-audit report and the annual
    compliance test report. Idempotent per form + period."""
    start_year = fy_end.year - 1
    quarters = [
        ("Q1", datetime.date(start_year, 7, 15)),
        ("Q2", datetime.date(start_year, 10, 15)),
        ("Q3", datetime.date(fy_end.year, 1, 15)),
        ("Q4", datetime.date(fy_end.year, 4, 15)),
    ]
    for label, due in quarters:
        add_obligation(
            db,
            entity_id,
            form_code="AIF-QR",
            title="SEBI AIF quarterly activity report",
            category="SEBI",
            due_date=due,
            period_label=f"{label} FY{fy_end.year}",
        )
    add_obligation(
        db,
        entity_id,
        form_code="AIF-PPM",
        title="Annual PPM audit report (to SEBI/trustee)",
        category="SEBI",
        due_date=fy_end + datetime.timedelta(days=180),
        period_label=f"FY{fy_end.year}",
    )
    add_obligation(
        db,
        entity_id,
        form_code="AIF-CTR",
        title="Annual compliance test report (Reg 20(6))",
        category="SEBI",
        due_date=fy_end + datetime.timedelta(days=30),
        period_label=f"FY{fy_end.year}",
    )
    db.commit()
    return (
        db.query(ComplianceObligation)
        .filter_by(entity_id=entity_id)
        .filter(ComplianceObligation.category == "SEBI")
        .count()
    )


def health_score(db: Session, entity_id: str, as_of: datetime.date) -> dict:
    obs = db.query(ComplianceObligation).filter_by(entity_id=entity_id).all()
    total = len(obs)
    filed = sum(
        1 for o in obs if o.status in (ObligationStatus.FILED, ObligationStatus.ACKNOWLEDGED)
    )
    overdue = sum(1 for o in obs if o.status in _OPEN and o.due_date < as_of)
    score = round(filed / total * 100) if total else 100
    return {
        "total": total,
        "filed": filed,
        "overdue": overdue,
        "open": total - filed,
        "score": score,
    }


def obligation_view(ob: ComplianceObligation, as_of: datetime.date) -> dict:
    overdue = ob.status in _OPEN and ob.due_date < as_of
    return {
        "id": ob.id,
        "form_code": ob.form_code,
        "title": ob.title,
        "category": ob.category,
        "period_label": ob.period_label,
        "due_date": ob.due_date,
        "status": ob.status,
        "assignee": ob.assignee,
        "srn": ob.srn,
        "overdue": overdue,
    }

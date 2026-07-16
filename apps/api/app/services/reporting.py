"""Periodic investor report (FR-K-4): assemble a metrics snapshot from the
entity's own records (cap table, valuation, fundraising, runway, compliance)
and combine it with founder-entered highlights into a shareable report."""
from sqlalchemy.orm import Session

from ..models.entity import LegalEntity
from .dashboard import entity_dashboard
from .finance import runway_summary


def report_metrics(db: Session, entity: LegalEntity) -> dict:
    d = entity_dashboard(db, entity)
    runway = runway_summary(db, entity.id)
    val = d.get("valuation", {})
    return {
        "shares_issued": d["cap_table"]["total_shares"],
        "stakeholders": d["cap_table"]["holders"],
        "capital_raised": d["cap_table"]["total_invested"],
        "fmv_per_share": val.get("fmv_per_share"),
        "valuation_date": val.get("valuation_date"),
        "open_rounds": d["fundraising"]["open_rounds"],
        "options_granted": d["esop"]["options_granted"],
        "runway_months": runway["runway_months"],
        "latest_cash": runway["latest_cash"],
        "monthly_burn": runway["avg_monthly_burn"],
        "compliance_overdue": d["compliance"]["overdue"],
    }


def _metrics_block(m: dict) -> str:
    rows = [
        ("Shares issued", f"{m['shares_issued']:,}"),
        ("Stakeholders", str(m["stakeholders"])),
        ("Capital raised (INR)", m["capital_raised"]),
        ("FMV per share (INR)", m["fmv_per_share"] or "—"),
        ("Latest valuation date", m["valuation_date"] or "—"),
        ("Open rounds", str(m["open_rounds"])),
        ("Options granted", f"{m['options_granted']:,}"),
        ("Cash in hand (INR)", m["latest_cash"] or "—"),
        ("Monthly burn (INR)", m["monthly_burn"] or "—"),
        ("Runway (months)", str(m["runway_months"]) if m["runway_months"] is not None else "—"),
        ("Overdue compliance items", str(m["compliance_overdue"])),
    ]
    return "\n".join(f"  {label}: {value}" for label, value in rows)


def build_report_data(db: Session, entity: LegalEntity, period_label: str, highlights: str) -> dict:
    m = report_metrics(db, entity)
    return {
        "company": entity.name,
        "period": period_label,
        "metrics": _metrics_block(m),
        "highlights": highlights or "—",
    }

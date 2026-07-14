"""Commercial contracts service (FR-Q): contract views with renewal status,
and a renewals-due query (overdue or upcoming within N days)."""
import datetime

from sqlalchemy.orm import Session

from ..models.clm import Contract, ContractStatus, Counterparty


def contract_view(db: Session, c: Contract, as_of: datetime.date) -> dict:
    cp = db.get(Counterparty, c.counterparty_id)
    days = (c.renewal_date - as_of).days if c.renewal_date else None
    overdue = (
        c.renewal_date is not None
        and c.renewal_date < as_of
        and c.status == ContractStatus.ACTIVE
    )
    return {
        "id": c.id,
        "counterparty_id": c.counterparty_id,
        "counterparty_name": cp.name if cp else None,
        "counterparty_kind": cp.kind.value if cp else None,
        "title": c.title,
        "type": c.type,
        "value": str(c.value) if c.value is not None else None,
        "currency": c.currency,
        "start_date": c.start_date,
        "end_date": c.end_date,
        "renewal_date": c.renewal_date,
        "auto_renew": c.auto_renew,
        "status": c.status,
        "document_id": c.document_id,
        "days_to_renewal": days,
        "renewal_overdue": overdue,
    }


def renewals_due(
    db: Session, entity_id: str, within_days: int, as_of: datetime.date
) -> list[dict]:
    horizon = as_of + datetime.timedelta(days=within_days)
    contracts = (
        db.query(Contract)
        .filter_by(entity_id=entity_id, status=ContractStatus.ACTIVE)
        .filter(Contract.renewal_date.isnot(None))
        .filter(Contract.renewal_date <= horizon)
        .order_by(Contract.renewal_date)
        .all()
    )
    return [contract_view(db, c, as_of) for c in contracts]

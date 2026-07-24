"""DDQ answer bank (Visible-style due-diligence support)."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ...models.fund import DDQEntry, Fund

DDQ_PRESETS = [
    {"category": "Firm", "question": "Describe the firm's history, ownership and organisational structure."},
    {"category": "Firm", "question": "Who are the key investment professionals and what are their backgrounds?"},
    {"category": "Fund", "question": "What is the fund's investment strategy and target portfolio construction?"},
    {"category": "Fund", "question": "What are the fund's key terms — size, management fee, carry, hurdle and life?"},
    {"category": "Track record", "question": "Provide the performance of prior funds (DPI / TVPI / IRR) and notable exits."},
    {"category": "Governance & compliance", "question": "Describe the fund's SEBI AIF registration and regulatory compliance framework."},
    {"category": "Governance & compliance", "question": "What is the valuation policy and who performs valuations?"},
    {"category": "Governance & compliance", "question": "Describe the conflicts-of-interest and related-party-transaction policies."},
    {"category": "Operations", "question": "Who are the fund's key service providers — administrator, auditor, custodian, legal counsel?"},
    {"category": "ESG", "question": "Describe the fund's ESG / responsible-investment policy and reporting."},
]


def _ddq_view(e: DDQEntry) -> dict:
    return {
        "id": e.id,
        "category": e.category,
        "question": e.question,
        "answer": e.answer,
        "answered": bool(e.answer and e.answer.strip()),
    }


def list_ddq(db: Session, fund: Fund) -> list[dict]:
    rows = (
        db.query(DDQEntry)
        .filter_by(fund_id=fund.id)
        .order_by(DDQEntry.category, DDQEntry.created_at)
        .all()
    )
    return [_ddq_view(e) for e in rows]


def create_ddq_entry(db: Session, fund: Fund, data: dict, user_id: str) -> dict:
    if db.query(DDQEntry).filter_by(fund_id=fund.id, question=data["question"]).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "This question is already in the bank")
    e = DDQEntry(
        fund_id=fund.id,
        category=(data.get("category") or "General").strip() or "General",
        question=data["question"].strip(),
        answer=data.get("answer"),
        created_by=user_id,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return _ddq_view(e)


def _get_ddq_entry(db: Session, fund: Fund, entry_id: str) -> DDQEntry:
    e = db.get(DDQEntry, entry_id)
    if e is None or e.fund_id != fund.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "DDQ entry not found")
    return e


def update_ddq_entry(db: Session, fund: Fund, entry_id: str, data: dict) -> dict:
    e = _get_ddq_entry(db, fund, entry_id)
    if data.get("category"):
        e.category = data["category"].strip()
    if data.get("question"):
        e.question = data["question"].strip()
    if "answer" in data:
        e.answer = data["answer"]
    db.commit()
    db.refresh(e)
    return _ddq_view(e)


def delete_ddq_entry(db: Session, fund: Fund, entry_id: str) -> None:
    db.delete(_get_ddq_entry(db, fund, entry_id))
    db.commit()


def ddq_sections(db: Session, fund: Fund) -> str:
    """The answer bank rendered as category sections for the DDQ document."""
    by_cat: dict[str, list[dict]] = {}
    for e in list_ddq(db, fund):
        by_cat.setdefault(e["category"], []).append(e)
    blocks = []
    for cat, entries in by_cat.items():
        lines = [cat.upper()]
        for i, e in enumerate(entries, 1):
            lines.append(f"  Q{i}. {e['question']}")
            lines.append(f"      {e['answer'].strip() if e['answered'] else '(response pending)'}")
        blocks.append("\n".join(lines))
    return ("\n\n".join(blocks) + "\n\n") if blocks else "No responses recorded yet.\n\n"

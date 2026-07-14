"""Cap-table CSV import (onboarding an existing company, FR-C).

CSV columns — required: stakeholder_name, security_class, quantity;
optional: stakeholder_type (founder/investor/employee/entity, default
investor), email, class_kind (equity/ccps/ccd/option_pool/safe/warrant,
default equity), price_per_unit (default 0), issue_date (YYYY-MM-DD,
default today).

Two-phase: `parse_and_validate` returns a full row-by-row report and
creates nothing; `apply_import` creates missing security classes and
stakeholders (matched by name) and appends one IssuanceTransaction per
row in a single transaction — all rows or none.
"""
import csv
import datetime
import io
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import Session

from ..clock import today_ist
from ..models.captable import (
    IssuanceTransaction,
    SecurityClass,
    SecurityKind,
    Stakeholder,
    StakeholderType,
)

REQUIRED = ["stakeholder_name", "security_class", "quantity"]
MAX_ROWS = 10_000
TEMPLATE = (
    "stakeholder_name,stakeholder_type,email,security_class,class_kind,"
    "quantity,price_per_unit,issue_date\n"
    "Aisha Sharma,founder,,Equity,equity,4000000,1,2024-05-01\n"
    "Blume Ventures,investor,ops@blume.vc,Seed CCPS,ccps,400000,100,2025-01-15\n"
)


def parse_and_validate(db: Session, entity_id: str, csv_text: str) -> dict:
    reader = csv.DictReader(io.StringIO(csv_text))
    headers = [h.strip() for h in (reader.fieldnames or [])]
    missing = [c for c in REQUIRED if c not in headers]
    if missing:
        return {"valid": False, "errors": [{"row": 0, "error": f"Missing column(s): {', '.join(missing)}"}],
                "rows": [], "summary": None}

    existing_classes = {c.name: c for c in db.query(SecurityClass).filter_by(entity_id=entity_id)}
    existing_holders = {s.name: s for s in db.query(Stakeholder).filter_by(entity_id=entity_id)}
    sh_types = {t.value for t in StakeholderType}
    kinds = {k.value for k in SecurityKind}

    rows, errors = [], []
    new_classes, new_holders = set(), set()
    total_shares = 0
    total_invested = Decimal("0")
    for i, raw in enumerate(reader, start=1):
        if i > MAX_ROWS:
            return {"valid": False, "rows": [], "summary": None,
                    "errors": [{"row": i, "error": f"Too many rows (max {MAX_ROWS})"}]}
        get = lambda k, d="": (raw.get(k) or d).strip()
        name = get("stakeholder_name")
        cls = get("security_class")
        problems = []
        if not name:
            problems.append("stakeholder_name is empty")
        if not cls:
            problems.append("security_class is empty")
        sh_type = get("stakeholder_type", "investor") or "investor"
        if sh_type not in sh_types:
            problems.append(f"stakeholder_type '{sh_type}' not in {sorted(sh_types)}")
        kind = get("class_kind", "equity") or "equity"
        if kind not in kinds:
            problems.append(f"class_kind '{kind}' not in {sorted(kinds)}")
        qty = 0
        try:
            qty = int(get("quantity") or "0")
            if qty <= 0:
                problems.append("quantity must be a positive integer")
        except ValueError:
            problems.append(f"quantity '{get('quantity')}' is not an integer")
        price = Decimal("0")
        try:
            price = Decimal(get("price_per_unit", "0") or "0")
            if price < 0:
                problems.append("price_per_unit must be >= 0")
        except InvalidOperation:
            problems.append(f"price_per_unit '{get('price_per_unit')}' is not a number")
        issue_date = today_ist()
        if get("issue_date"):
            try:
                issue_date = datetime.date.fromisoformat(get("issue_date"))
            except ValueError:
                problems.append(f"issue_date '{get('issue_date')}' is not YYYY-MM-DD")

        if problems:
            errors.append({"row": i, "error": "; ".join(problems)})
            continue
        if name not in existing_holders:
            new_holders.add(name)
        if cls not in existing_classes:
            new_classes.add(cls)
        total_shares += qty
        total_invested += Decimal(qty) * price
        rows.append({
            "stakeholder_name": name, "stakeholder_type": sh_type,
            "email": get("email") or None, "security_class": cls, "class_kind": kind,
            "quantity": qty, "price_per_unit": price, "issue_date": issue_date,
        })

    existing_issuances = (
        db.query(IssuanceTransaction).filter_by(entity_id=entity_id).count()
    )
    return {
        "valid": not errors,
        "errors": errors,
        "rows": rows,
        "summary": {
            "issuances": len(rows),
            "stakeholders_to_create": sorted(new_holders),
            "classes_to_create": sorted(new_classes),
            "total_shares": total_shares,
            "total_invested": str(total_invested),
            "warning": (
                f"Entity already has {existing_issuances} issuance(s); importing appends to the ledger."
                if existing_issuances else None
            ),
        },
    }


def apply_import(db: Session, entity_id: str, rows: list[dict]) -> dict:
    classes = {c.name: c for c in db.query(SecurityClass).filter_by(entity_id=entity_id)}
    holders = {s.name: s for s in db.query(Stakeholder).filter_by(entity_id=entity_id)}
    created_classes = created_holders = 0
    for r in rows:
        if r["security_class"] not in classes:
            sc = SecurityClass(entity_id=entity_id, name=r["security_class"],
                               kind=SecurityKind(r["class_kind"]))
            db.add(sc)
            db.flush()
            classes[sc.name] = sc
            created_classes += 1
        if r["stakeholder_name"] not in holders:
            sh = Stakeholder(entity_id=entity_id, name=r["stakeholder_name"],
                             type=StakeholderType(r["stakeholder_type"]), email=r["email"])
            db.add(sh)
            db.flush()
            holders[sh.name] = sh
            created_holders += 1
        db.add(IssuanceTransaction(
            entity_id=entity_id,
            security_class_id=classes[r["security_class"]].id,
            stakeholder_id=holders[r["stakeholder_name"]].id,
            quantity=r["quantity"],
            price_per_unit=r["price_per_unit"],
            issue_date=r["issue_date"],
        ))
    db.commit()
    return {
        "classes_created": created_classes,
        "stakeholders_created": created_holders,
        "issuances_created": len(rows),
    }

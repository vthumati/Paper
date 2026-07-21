"""Full teardown of an entity or workspace and everything that hangs off it.

This is the destructive counterpart to the safe empty-only workspace delete.
It walks the foreign-key graph from a root row (a legal entity, or a tenant)
and deletes the entire subtree of rows that reference it, transitively — so
indirectly-owned records (an ESOP grant hanging off a stakeholder, a round
commitment, a drawdown notice) go too, without hard-coding table names.

The same closure powers a dry-run **preview** (row counts per area) that the
UI shows before asking the user to type the name to confirm.
"""
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — ensure every model is registered on the metadata
from app.models.base import Base

# child rows are deleted in chunks to stay under SQLite's parameter limit
_CHUNK = 400

# friendly labels for the preview breakdown; unmapped tables fall back to a
# prettified table name
_LABELS = {
    "legal_entities": "Entity",
    "tenants": "Workspace",
    "memberships": "Members",
    "issuance_transactions": "Cap-table issuances",
    "security_classes": "Share classes",
    "stakeholders": "Stakeholders",
    "esop_schemes": "ESOP schemes",
    "esop_grants": "ESOP grants",
    "documents": "Documents",
    "compliance_obligations": "Compliance obligations",
    "rounds": "Rounds",
    "convertible_instruments": "SAFEs / notes",
    "funds": "Funds",
    "portfolio_investments": "Portfolio investments",
    "data_rooms": "Data rooms",
    "resolutions": "Resolutions",
    "meetings": "Board meetings",
}


def _children_index():
    """parent-table-name -> [(child_table, child_fk_column, parent_column)]."""
    idx = defaultdict(list)
    for table in Base.metadata.tables.values():
        for fk in table.foreign_keys:
            idx[fk.column.table.name].append((table, fk.parent, fk.column))
    return idx


def _pk(table):
    return list(table.primary_key.columns)[0]


def _closure(db: Session, root_table: str, root_ids: set[str]) -> dict[str, set]:
    """All rows reachable by following incoming FKs from the root rows —
    table-name -> set of primary-key values (the root table included)."""
    idx = _children_index()
    doomed: dict[str, set] = defaultdict(set)
    doomed[root_table] |= set(root_ids)
    frontier = [(root_table, set(root_ids))]
    while frontier:
        nxt = []
        for parent_table, parent_ids in frontier:
            if not parent_ids:
                continue
            for child, child_fk, _parent_col in idx.get(parent_table, []):
                found: set = set()
                ids = list(parent_ids)
                for i in range(0, len(ids), _CHUNK):
                    rows = db.execute(
                        select(_pk(child)).where(child_fk.in_(ids[i : i + _CHUNK]))
                    ).scalars().all()
                    found.update(rows)
                fresh = found - doomed[child.name]
                if fresh:
                    doomed[child.name] |= fresh
                    nxt.append((child.name, fresh))
        frontier = nxt
    return doomed


def _label(table_name: str) -> str:
    return _LABELS.get(table_name, table_name.replace("_", " ").capitalize())


def _preview(doomed: dict[str, set], root_table: str) -> dict:
    """Human-readable breakdown of a closure: associated-record counts by area
    (the root row itself excluded) plus the total row count that will go."""
    breakdown = {
        _label(name): len(ids)
        for name, ids in doomed.items()
        if ids and name != root_table
    }
    breakdown = dict(sorted(breakdown.items(), key=lambda kv: -kv[1]))
    associated = sum(breakdown.values())
    return {"associated_records": associated, "total_rows": associated + 1, "breakdown": breakdown}


def _delete_closure(db: Session, doomed: dict[str, set]) -> int:
    """Delete every doomed row, children before parents where the FK graph is
    acyclic (order is irrelevant on SQLite, which has FK checks off, but keeps
    the operation valid on databases that enforce them)."""
    try:
        order = list(reversed(Base.metadata.sorted_tables))
    except Exception:  # circular FK graph — order can't matter under SQLite
        order = list(Base.metadata.tables.values())
    total = 0
    for table in order:
        ids = doomed.get(table.name)
        if not ids:
            continue
        ids = list(ids)
        for i in range(0, len(ids), _CHUNK):
            res = db.execute(delete(table).where(_pk(table).in_(ids[i : i + _CHUNK])))
            total += res.rowcount or 0
    return total


# --- entity ------------------------------------------------------------------
def preview_entity_teardown(db: Session, entity) -> dict:
    doomed = _closure(db, "legal_entities", {entity.id})
    return {"name": entity.name, **_preview(doomed, "legal_entities")}


def teardown_entity(db: Session, entity) -> int:
    doomed = _closure(db, "legal_entities", {entity.id})
    deleted = _delete_closure(db, doomed)
    db.commit()
    return deleted


# --- workspace (tenant) ------------------------------------------------------
def preview_workspace_teardown(db: Session, tenant) -> dict:
    doomed = _closure(db, "tenants", {tenant.id})
    return {"name": tenant.name, **_preview(doomed, "tenants")}


def teardown_workspace(db: Session, tenant) -> int:
    doomed = _closure(db, "tenants", {tenant.id})
    deleted = _delete_closure(db, doomed)
    db.commit()
    return deleted

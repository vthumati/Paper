# Paper API

Phase 1 backend for **Paper** — see `../../REQUIREMENTS.md` and `../../HLD.md`.

FastAPI + SQLAlchemy. Local dev uses SQLite (zero setup); Postgres in staging/prod.

## What's implemented (Phase 1, slice 1)

- **Identity** — users, JWT auth (signup/login/me), tenants, memberships, RBAC.
- **Entity** — legal entities scoped to a tenant.
- **CapTable** — security classes, stakeholders, an **append-only issuance ledger**,
  and a **cap-table projection** computed from the ledger (ADR-2).
- **Workflow engine** (HLD §7) — versioned definitions as data, persisted runs/steps,
  suspend-resume, and **conditional branching** (e.g. foreign-investor → FC-GPR step).
  Seeded definitions: `priced_round`, `incorporate_pvt_ltd`.

Tenant isolation is enforced at the app layer (RBAC); Postgres Row-Level Security
(ADR-5) is added with the Postgres migration.

## Run

```bash
cd apps/api
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate; pip install -r requirements.txt  # *nix

# tests
.venv\Scripts\python -m pytest -q

# dev server
.venv\Scripts\python -m uvicorn app.main:app --reload
# OpenAPI docs at http://127.0.0.1:8000/docs

# seed a full demo workspace (login: demo@acme.in / demo-pass-123)
.venv\Scripts\python scripts\seed_demo.py --fresh

# schema migrations (prod path; dev auto-creates tables)
.venv\Scripts\python -m alembic upgrade head
```

- **Document + e-Sign** — templates as data, generated documents with
  append-only versioning, simulated Aadhaar e-Sign (request → callback → signed),
  and workflow `generate-document` / `request-signature` steps wired to real
  module actions.
- **Data Room** — scoped rooms, items linking documents, access grants, and
  view engagement logging (FR-I).
- **Compliance calendar** — statutory ROC obligations generated from the FY end
  via a rules registry, with overdue tracking and status transitions (FR-H).

A React + Vite frontend lives in `../web` (login, organisations, entities, and
an entity workspace with Cap Table / Workflows / Documents / Data Room /
Compliance tabs).

## Next (post-Phase 1)

Postgres migration (Alembic + Row-Level Security, ADR-5); then Phase 2
(Fund admin / AIF, SPV, full ESOP, valuations, services marketplace).

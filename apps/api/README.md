# Paper API

Backend for **Paper** — see `../../REQUIREMENTS.md` (what it does, per-FR status),
`../../HLD.md` (architecture + as-built addendum) and `../../DEPLOYMENT.md`
(deferred infra plan).

FastAPI + SQLAlchemy 2.0. Local dev uses SQLite (zero setup); Postgres in
staging/prod via `PAPER_DATABASE_URL`. **174 tests.**

## What's here

21 bounded contexts (modules A–U of the requirements) over an **event-sourced
cap table** (ADR-2): issuances/transfers/conversions/buybacks/splits/rights
replayed on read — cap table, fully-diluted view, waterfall and fund capital
accounts are projections, never stored balances.

Highlights: stage-guided workspace (inception → pre-seed → seed → series →
pre-IPO), SAFEs/notes with the Sec 42 offeree guardrail and auto-conversion at
round close, ESOP with valuation-priced exercise, governance with investor
consents, compliance engine (ROC/GST/FEMA/SEBI-AIF, event-based filings), fund
administration (waterfall with hurdle + GP catch-up, fees, units, DPI/TVPI/XIRR,
deal pipeline, LP statements, Form 64C/64D), investor/LP/employee portal, and
secondary sales with ROFR. All recorded times are IST (`app/clock.py`, ADR-8).

## Run

```bash
cd apps/api
py -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt   # Windows
# source .venv/bin/activate; pip install -r requirements.txt  # *nix

# tests
.venv\Scripts\python -m pytest -q

# dev server (auto-creates tables; http://127.0.0.1:8000/docs)
.venv\Scripts\python -m uvicorn app.main:app --reload

# seed a full demo workspace (login: demo@acme.in / demo-pass-123)
.venv\Scripts\python scripts\seed_demo.py --fresh

# schema migrations (prod path; dev auto-creates behind PAPER_AUTO_CREATE_TABLES)
.venv\Scripts\python -m alembic upgrade head
```

The React frontend lives in `../web` (`npm install && npm run dev`).

## Next

Deployment (Cloud SQL + RLS + Cloud Run per `DEPLOYMENT.md`), email delivery +
production auth, PDF rendering for generated documents, cap-table import.
External integrations (e-sign/KYC/payments/MCA21/FIRMS) await credentials —
the e-sign flow runs end-to-end against a simulated provider.

# Paper — Deployment & Deferred Infra

Status: planned (not yet started) · Companion to: `HLD.md` §11

This file tracks the one remaining piece of foundational work, deliberately
**deferred** until a Postgres instance is provisioned so it can be done and
verified together with deployment.

## Decision

The **Postgres migration (Alembic + Row-Level Security)** is deferred and will be
done **alongside deployment** (Cloud SQL + Cloud Run + WIF, per `HLD.md` §11),
because verifying RLS meaningfully requires a real Postgres instance — it cannot
be exercised on the dev SQLite database.

Until then the backend runs on SQLite with `Base.metadata.create_all` at startup
(see `apps/api/app/main.py`), which is correct for local dev. The app is already
Postgres-ready: `PAPER_DATABASE_URL` switches the engine (`apps/api/app/db.py`),
and all money/share math uses `Decimal`/`Numeric`.

## Deferred work (when Cloud SQL exists)

1. ~~**Alembic**~~ **DONE (2026-06-28)** — Alembic is scaffolded at `apps/api/alembic/`
   with a verified baseline migration (`a64b6c407af7`, 67-table parity with the
   models; `render_as_batch` for SQLite-safe ALTERs). Dev still auto-creates
   tables; production sets `PAPER_AUTO_CREATE_TABLES=false` and runs
   `python -m alembic upgrade head`.
2. **Row-Level Security (ADR-5)** — enable RLS on tenant-scoped tables and add
   policies keyed off a per-request `SET app.current_tenant`, as defence-in-depth
   behind the existing app-layer RBAC. Postgres-only migration (dialect-guarded).
3. **Verify RLS** against the live Postgres: cross-tenant access must fail at the
   DB layer even with app checks bypassed.
4. **Production env config** — set `PAPER_ENVIRONMENT=prod` (the app refuses to
   boot with the default `PAPER_JWT_SECRET` outside dev/test) and swap the
   in-memory login rate-limiter for a Redis-backed one when multi-instance.
5. **Timezone note** — all recorded times are IST at the application layer
   (`app/clock.py`, NFR-13), so Cloud Run's UTC host clock needs no changes.
   Keep writes going through the ORM (Python-side IST defaults); the columns'
   `server_default CURRENT_TIMESTAMP` fallback is UTC and only fires on raw SQL
   inserts — avoid those, or set the Cloud SQL database default
   `timezone = 'Asia/Kolkata'` as belt-and-braces.

## Deployment (target, per HLD §11)

- **Compute:** `api` (+ later a `worker`) on **Cloud Run**, autoscaling, multi-zone.
- **Data:** **Cloud SQL** Postgres (HA + PITR) + read replica; **GCS** (India region,
  CMEK) for documents; **Memorystore** (Redis) for cache/locks.
- **CI/CD:** **GitHub Actions + Workload Identity Federation** (no static keys) →
  Artifact Registry → Cloud Run. Mirrors the org's SMS/CyberAI pattern.
- **Secrets/keys:** Secret Manager + Cloud KMS. **IaC:** Terraform.
- **Config:** set `PAPER_DATABASE_URL` (Postgres DSN), `PAPER_JWT_SECRET` (32B+),
  and `PAPER_CORS_ORIGINS` per environment (dev → staging → prod, separate projects).

## Current state (for context)

Phases 1 + 2 are functionally complete: 11 modules, **52 backend tests passing**,
full React frontend. See `REQUIREMENTS.md`, `HLD.md`, and `apps/api/README.md`.

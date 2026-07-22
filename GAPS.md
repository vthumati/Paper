# Paper — Gaps & Improvements

A living list of known gaps, grounded in the codebase. **Much of what's "missing" is
deliberate MVP scope, not defects** — those are separated out under §4. Companion to
[`todo.txt`](todo.txt) (which tracks the deferred AI layer specifically).

Legend: **[P1]** blocks real-world use · **[P2]** high-leverage prod fix · **[P3]** quality/robustness.

---

## 1. Production-readiness gaps (fix before real customers)

- **[P1] No binary file upload / storage.** There is no `UploadFile` anywhere in the API.
  Documents are generated from templates (`apps/api/app/documents/templates.py`) and the
  data room shares those; a user cannot upload their own files (signed SHAs, board minutes,
  financial statements, KYC/ID docs, pitch decks). Document custody is table stakes for an
  "OS for corporate legal." Needs: upload endpoints + a storage backend (GCS/S3) + virus/size
  limits + linking uploads to entities/data rooms/documents.

- **[P1] No real notification delivery.** "Send reminders", capital-call notices, consent
  requests and KPI requests write `Notification` rows shown **in-app only** — there is no
  email/SMS integration (verified: no smtp/sendgrid/ses/resend in the API). Investors, LPs
  and founders see nothing unless they log in. Needs: an email provider wired to the existing
  notification records (+ digest/scheduling).

- **[P1] E-sign is simulated.** `apps/api/app/services/document.py` explicitly fakes the
  provider callback (`Simulate the verified provider callback`). "Signed" documents are not
  legally executed. Needs: a real provider (Digio / NSDL/Protean Aadhaar eSign / DocuSign).

- **[P2] Rate limiting is in-memory.** `apps/api/app/ratelimit.py` is an in-process sliding
  window. On Cloud Run (horizontal scaling + cold starts) it is per-instance and resets on
  restart, so it is easily bypassed. Move to Redis / shared store for prod.

- **[P2] JWT / session hardening.** Default secret is `dev-insecure-change-me...`
  (`apps/api/app/config.py`) — safe only if `PAPER_JWT_SECRET` is set in deploy. No
  server-side revocation (logout is client-only) and no refresh tokens; a leaked 12h token
  cannot be killed. Consider refresh tokens + a revocation list, and assert a non-default
  secret at startup in prod.

- **[P2] PDF Unicode.** `apps/api/app/services/pdf.py` uses fpdf2 **core fonts** (Latin-1),
  so the ₹ glyph and non-Latin stakeholder names likely will not render in generated PDFs.
  Embed a Unicode TTF (e.g. Noto Sans).

## 2. Correctness / fidelity (numbers are a planning model, not audit-grade)

The financial engines are honest about this in-code and it is acceptable for an MVP, but they
need hardening before customers rely on them for statutory filings / audits.

- **Fund accounting** (`services/fund.py`, `services/fund_perf.py`): uninvested fund cash is
  not tracked in NAV; preferred return keeps accruing on all paid-in capital; waterfall is
  simplified; XIRR needs dated cashflows to populate.
- **Cap table** (`services/captable.py`): as-converted election for non-participating
  preferred is simplified.
- **ESOP expense — Ind AS 102** (`services/sbp.py`): forfeiture/true-up and graded
  per-tranche vesting curves are simplified.

## 3. Quality & robustness

- **[P3] Frontend test coverage is thin: 3 test files for ~92 components** (backend is
  well covered — 84 test files). No component/interaction/e2e tests, so UI regressions rely
  on manual checking. Add component tests for the high-traffic surfaces (Dashboard, Cap Table,
  Fund, Portal, EntityDetail nav) and a smoke e2e for the founder + fund journeys.
- **[P3] Partial pagination.** activity/compliance/documents/workspace paginate; cap-table,
  stakeholders, LPs, holdings and deal lists appear to return all rows unbounded. Fine at demo
  scale, a problem at portfolio scale.
- **[P3] Permission granularity.** Owner-only teardown and a membership model exist, but
  fine-grained roles (viewer/editor/admin, per-tab scoping) were not found — audit before
  multi-user firms rely on it.
- **[P3] India-only currency.** Models default to INR and the UI hardcodes ₹; no FX /
  multi-currency for cross-border LPs or USD funds.

## 4. Deliberate roadmap (documented exclusions — not bugs)

- **AI layer — 8 features deferred** (see [`todo.txt`](todo.txt)): AI inbox, AI updates,
  document extraction, portfolio chat, MCP server, DDQ drafting, CRM note capture, compliance
  copilot. Gated on wiring an LLM provider (default to latest Claude models).
- **Money movement excluded** — capital calls / distributions / investments are *recorded*,
  not *executed* (no NACH/UPI/bank rails).
- **No GL export** for fund financials (intentional).
- **Cross-tenant SPV linkage deferred** (`apps/api/app/routes/spv.py` — same-tenant only for now).

## Suggested priority order

1. **File upload/storage** + **email delivery** — these two block genuine day-to-day usage
   more than anything else.
2. **Rate-limit + JWT/session hardening** + **PDF Unicode font** — small, high-leverage prod fixes.
3. **Frontend test coverage** — pay down before the next big feature push.
4. Fidelity work (fund accounting → audit-grade) as customers demand it; the AI layer once an
   LLM key is available.

# Paper — Gaps & Improvements

A living list of known gaps, grounded in the codebase. **Much of what's "missing" is
deliberate MVP scope, not defects** — those are separated out under §4. Companion to
[`todo.txt`](todo.txt) (which tracks the deferred AI layer specifically).

Legend: **[P1]** blocks real-world use · **[P2]** high-leverage prod fix · **[P3]** quality/robustness.

---

## 0. Recently resolved (2026-07-24)

- ✅ **Email case-sensitivity** — every email address field is normalised (trim + lower) at
  the schema boundary; signup/login and the advisor cross-tenant match are case-insensitive.
  No more duplicate accounts or case-based access misses.
- ✅ **JWT revocation** — `User.token_version` embedded in the token and checked per request;
  `POST /auth/logout` bumps it, revoking all outstanding tokens. *(Refresh tokens and a
  startup assertion for a non-default secret are still open — see §1.)*
- ✅ **Unbounded queries** — stakeholders, LPs, deals, portfolio holdings and SPV co-investors
  now paginate (shared `page` dep, default 100 / max 500). *(Other lists can adopt it as
  needed — see §3.)*
- ✅ **E-sign bypass (interim)** — completing a signature now requires a one-time completion
  token issued at request time, not generic workspace write access. *(Still a simulated
  provider; real Digio/Aadhaar eSign integration remains a P1 — see §1.)*
- ✅ **`fund.py` monolith decomposed** — `services/fund.py` (1,945 ln) and `routes/fund.py`
  (1,690 ln) split into subdomain packages (`profile / accounting / prospects / deals /
  monitoring / ddq`), behavior-preserving (public API + route paths unchanged).

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

- **[P1] E-sign is simulated.** Completion is now token-gated (interim hardening, §0), but it
  is still a **simulated** provider — "signed" documents are not legally executed. Needs: a
  real provider (Digio / NSDL/Protean Aadhaar eSign / DocuSign) whose verified callback
  replaces the token shim in `apps/api/app/services/document.py`.

- **[P2] Rate limiting is in-memory.** `apps/api/app/ratelimit.py` is an in-process sliding
  window. On Cloud Run (horizontal scaling + cold starts) it is per-instance and resets on
  restart, so it is easily bypassed. Move to Redis / shared store for prod.

- **[P2] JWT / session hardening.** Server-side revocation now exists (`token_version`, §0).
  Still open: **refresh tokens** (access token lives 12h), and a **startup assertion** that
  `PAPER_JWT_SECRET` is not the `dev-insecure-change-me...` default (`apps/api/app/config.py`)
  in prod.

- **[P2] PDF Unicode.** `apps/api/app/services/pdf.py` uses fpdf2 **core fonts** (Latin-1),
  so the ₹ glyph and non-Latin stakeholder names likely will not render in generated PDFs.
  Embed a Unicode TTF (e.g. Noto Sans).

## 2. Correctness / fidelity (numbers are a planning model, not audit-grade)

The financial engines are honest about this in-code and it is acceptable for an MVP, but they
need hardening before customers rely on them for statutory filings / audits.

- **Fund accounting** (`services/fund/accounting.py`, `services/fund_perf.py`): uninvested fund cash is
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
- **[P3] Partial pagination.** The largest collections now paginate (activity, compliance,
  documents, workspace, **stakeholders, LPs, deals, portfolio holdings, SPV co-investors** —
  §0). A few smaller list endpoints still return all rows; adopt the shared `page` dep there
  too as data grows. No "load more" UI yet (frontend requests the 500 cap).
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
   more than anything else. (Real e-sign provider pairs with file upload.)
2. **Rate-limit → shared store** + **refresh tokens / non-default-secret assertion** +
   **PDF Unicode font** — small, high-leverage prod fixes.
3. **Frontend test coverage** — pay down before the next big feature push.
4. Fidelity work (fund accounting → audit-grade) as customers demand it; the AI layer once an
   LLM key is available.

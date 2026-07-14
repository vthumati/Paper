# Paper — High-Level Design (HLD)

**An "operating system for corporate legal" for Indian startups and funds.**

Status: Draft v0.1 · Date: 2026-06-25 · Companion to: `REQUIREMENTS.md`

---

## 1. Introduction

### 1.1 Purpose
This High-Level Design describes the architecture of **Paper** — the system whose capabilities are specified in `REQUIREMENTS.md`. It defines the logical decomposition, technology stack, data and integration architecture, the workflow engine, key runtime flows, security, and deployment. It is the bridge between *what* the product must do (requirements) and *how* engineering builds it (low-level design / implementation).

### 1.2 Scope
Covers the platform that serves both customer types — **startups/operating companies** and **funds (SEBI AIFs)** — across the 20 functional modules (A–T) and the non-functional requirements. Low-level schema DDL, API contracts per endpoint, and UI wireframes are out of scope (deferred to LLD/API spec/design files).

### 1.3 Audience
Engineering leads, architects, security/compliance reviewers, and the product team.

### 1.4 References
- `REQUIREMENTS.md` — functional (FR-A..T) and non-functional (NFR-1..11) requirements, conceptual data model (§6).
- PaperOS capability grounding: [paperos.com](https://paperos.com/plans), [learn.paperos.com](https://learn.paperos.com/).

### 1.5 Definitions
AIF (Alternative Investment Fund), CCPS/CCD (compulsorily convertible preference shares / debentures), FC-GPR/FC-TRS (RBI foreign-investment filings), DSC (Digital Signature Certificate), RTA (Registrar & Transfer Agent), DPDP (Digital Personal Data Protection Act 2023), RBAC (role-based access control), SoT (source of truth).

### 1.6 Stated assumptions (design inputs)
> These shape the design; flag if any is wrong.
1. Cloud is **GCP** with deploys to **Cloud Run** via GitHub Actions + Workload Identity Federation — consistent with the org's other platforms.
2. Primary stack is **Python/FastAPI** services + **React (Vite)** SPA + **PostgreSQL**, matching the org's existing apps.
3. We **prepare and assist** statutory filings; licensed professionals (CS/CA/merchant banker) review and file where law requires. Paper is not itself a regulated intermediary, payment gateway, or RTA.
4. India-first: data residency in India, INR base currency, English-first UI.
5. Build-vs-buy favours **integrating** specialist providers for e-sign, KYC, payments, valuation and demat rather than building them.

---

## 2. Architectural Goals & Constraints

| Driver (from NFR) | Architectural implication |
|---|---|
| Single source of truth, traceability (NFR-7) | Append-only transaction ledgers; derived snapshots; every record links to a source document. |
| Auditability (NFR-4) | Centralised immutable audit log; all mutations flow through the workflow/command layer. |
| Security & tenant isolation (NFR-1, 11) | Tenant-scoped data access enforced at the data layer; least-privilege RBAC; encryption at rest/in transit. |
| Data residency & privacy (NFR-2, 3) | India region pinning; DPDP consent/retention; PII segregation. |
| Availability 99.9% (NFR-5) | Stateless services, managed Postgres with HA, multi-zone Cloud Run. |
| Regulation changes often | Rules (forms, deadlines, valuation methods) externalised as **data/config**, not hard-coded. |
| Two personas, many modules | Modular decomposition with a shared core; module enable/disable per tenant type. |

**Key constraint:** statutory logic must be *versioned and config-driven* so that a change in the Companies Act, FEMA pricing, or SEBI AIF rules is a data update, not a code rewrite.

---

## 3. Architecture Overview

### 3.1 Style
A **modular monolith with a service-oriented seam** — a single deployable backend organised into strongly-bounded modules (the A–T domains), fronted by an API gateway, with a small number of independently-scaled workers (async jobs, document rendering, e-sign callbacks). This avoids premature microservice sprawl while keeping clean module boundaries that can be peeled off into services later (e.g., the Fund Admin module, or Document rendering).

Rationale: the domains share a dense relational core (the cap-table/party/document spine in §6 of requirements); a distributed model would force chatty cross-service joins early. Start modular-monolith; extract on proven scaling pressure.

### 3.2 Logical view (C4 container level)

```
                         ┌───────────────────────────────────────────┐
   Browser (React SPA)   │            Web / Mobile clients             │
   Investor/LP portal    └───────────────────┬─────────────────────────┘
                                              │ HTTPS / JSON
                                  ┌───────────▼───────────┐
                                  │     API Gateway        │  authn, rate-limit,
                                  │   (FastAPI edge)       │  tenant resolution
                                  └───────────┬───────────┘
                                              │
        ┌─────────────────────────────────────┼─────────────────────────────────────┐
        │                 PAPER BACKEND (modular monolith)                            │
        │                                                                             │
        │  Domain modules (A–T):                                                      │
        │  Identity/RBAC · Entity · CapTable · ESOP · Fundraising · Governance ·      │
        │  Compliance · DataRoom · FundAdmin(AIF) · Valuation · CLM · Team · SPV      │
        │                                                                             │
        │  Cross-cutting platform services:                                           │
        │  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐       │
        │  │ Workflow     │ │ Document &    │ │ Notification │ │ Audit &      │       │
        │  │ Engine (N)   │ │ Template svc  │ │ service      │ │ Activity log │       │
        │  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘       │
        └───────┬───────────────────┬───────────────────┬───────────────┬────────────┘
                │                   │                   │               │
        ┌───────▼──────┐   ┌────────▼───────┐   ┌────────▼──────┐  ┌─────▼─────────┐
        │ PostgreSQL   │   │ Object storage │   │ Job queue +   │  │ Cache         │
        │ (primary +   │   │ (documents,    │   │ workers       │  │ (Redis)       │
        │  read replica)│   │  data room)    │   │ (Cloud Tasks) │  └───────────────┘
        └──────────────┘   └────────────────┘   └───────────────┘
                                              │
                                  ┌───────────▼───────────────────────────┐
                                  │   External Integration Adapters         │
                                  │  e-Sign · KYC/DigiLocker · MCA21 ·      │
                                  │  RBI FIRMS · Payments/escrow ·          │
                                  │  Accounting · Valuer · NSDL/CDSL        │
                                  └─────────────────────────────────────────┘
```

### 3.3 Architectural layers
1. **Presentation** — React SPA (founder/CFO/CS app; fund GP/admin app; investor/LP portal as scoped views), server-driven workflow UI.
2. **API / application** — FastAPI gateway + per-module routers; command/query handlers; workflow orchestration.
3. **Domain** — module domain logic (cap-table math, waterfall, vesting, compliance-rule evaluation), persistence-agnostic.
4. **Data** — PostgreSQL (transactional + ledger), object storage (documents), Redis (cache/locks), search index.
5. **Integration** — adapter layer behind stable internal interfaces (anti-corruption layer per external provider).

---

## 4. Module Decomposition

Each requirement module maps to a backend bounded context. Cross-cutting modules (N, M, T) are platform services every domain consumes.

| Module | Bounded context | Core responsibilities | Depends on |
|---|---|---|---|
| A | **Identity** | Tenants, users, memberships, RBAC, KYC profiles | — |
| B | **Entity** | Legal entities, corporate record, registers, registrations | Identity, Document |
| C | **CapTable** | Security classes, holdings, issuance ledger, snapshots, transfers, stamp duty | Entity, Document, Workflow |
| D | **ESOP** | Schemes, grants, vesting, exercise | CapTable, Valuation |
| E | **Fundraising** | Rounds, term sheets, commitments, deal docs, closing | CapTable, DataRoom, Compliance |
| F | **Document** (platform) | Templates, generation/merge, versions, e-sign orchestration | Workflow, Integration |
| G | **Governance** | Meetings, resolutions, consents, indemnification | Entity, Document |
| H | **Compliance** | Obligation generation, filing tasks, FEMA/ROC prep, calendar | Entity, Valuation, Notification |
| I | **DataRoom** | Rooms, access grants, engagement analytics | Document, Entity |
| J | **FundAdmin** | Funds, LPs, commitments, capital accounts, calls, distributions, portfolio | Identity, Document, Compliance |
| K | **Portal** | Investor/LP dashboards, updates, statements | CapTable, FundAdmin, Document |
| L | **Valuation** | Valuation requests/reports, method/rule tracking | Entity, Integration |
| M | **Integration** (platform) | Adapters, webhooks, audit | all |
| N | **Workflow** (platform) | Workflow definitions/runs/steps engine | all |
| O | **Services** | Partner network, engagements | Identity, Document |
| P | **ManagedAdmin** | Subscriptions, touchpoints, audit engagements | all |
| Q | **CLM** | Counterparties, contracts, obligations | Document |
| R | **Team** | Team registry, HR-legal docs | Identity, ESOP, Document |
| S | **SPV** | Single-deal vehicles (reuses FundAdmin primitives) | FundAdmin |
| T | **Workspace/Reporting** (platform) | Workspaces, file cabinet, dashboards, tax records, reports | all |

---

## 5. Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Frontend | React + Vite + TypeScript; component lib (e.g., MUI); TanStack Query | Org standard; SPA with role-scoped views. |
| API | FastAPI (Python 3.12+), Pydantic v2, async | Org standard; strong typing, OpenAPI out of the box. |
| Domain logic | Python services; `decimal`-based money/share math | Precision-critical cap-table & waterfall computations. |
| Primary DB | PostgreSQL 16 (Cloud SQL HA) + read replica | Relational core, JSONB for flexible terms, row-level security for tenant isolation. |
| Object storage | GCS buckets (India region), per-tenant prefixes, CMEK | Documents, data-room files, signed PDFs. |
| Cache / locks | Redis (Memorystore) | Session, rate-limit, distributed locks for ledger writes. |
| Async / jobs | Cloud Tasks + worker Cloud Run service | e-sign callbacks, doc rendering, reminders, report generation. |
| Search | Postgres FTS initially; OpenSearch if needed | Document/file-cabinet search. |
| Document rendering | HTML/template → PDF (headless renderer); DOCX via templating | Template merge (FR-F-2). |
| Workflow | In-house lightweight engine (definitions as data) | Backbone for FR-N; avoids heavyweight BPM. |
| AuthN | OIDC/SSO + email-OTP; MFA | FR-A-3. |
| Infra | GCP Cloud Run, Cloud SQL, GCS, Cloud Tasks, Secret Manager | Org standard; serverless scaling. |
| CI/CD | GitHub Actions + Workload Identity Federation | Org standard (matches SMS/CyberAI pattern). |
| IaC | Terraform | Reproducible environments. |
| Observability | Cloud Logging/Monitoring/Trace; structured logs | NFR-5 ops. |

---

## 6. Data Architecture

### 6.1 Stores
- **PostgreSQL (system of record):** all structured domain data — the party/entity/cap-table/fund spine from `REQUIREMENTS.md §6`. JSONB for variable instrument terms and workflow step payloads.
- **Object storage (GCS):** immutable document blobs and data-room files; DB holds metadata + references; signed-PDF originals retained for tamper evidence.
- **Redis:** ephemeral cache and locks.
- **Search index:** document/contract/file-cabinet full-text.

### 6.2 Multi-tenancy
- **Shared schema, tenant-scoped rows** with a mandatory `tenant_id` and **PostgreSQL Row-Level Security** policies — defence-in-depth so an application bug cannot leak cross-tenant data.
- Object storage partitioned by tenant prefix with per-tenant CMEK keys.
- **Cross-tenant linkage** (fund ↔ portfolio company cap table) handled by an explicit, consent-gated *sharing grant* rather than shared rows.

### 6.3 Ledger & snapshot pattern
Cap-table and capital-account state are **derived**, not stored as mutable balances:
- Append-only `IssuanceTransaction` / `Transfer` / `ConversionEvent` (CapTable) and `CapitalCall` / `Distribution` (FundAdmin) events.
- `CapTableSnapshot` / `CapitalAccount` are materialised projections, recomputable from the ledger, stamped with effective date and source document.
- Guarantees NFR-7 traceability and supports time-travel ("cap table as of date X").

### 6.4 Document as first-class object
`Document` carries a polymorphic `subject_type/subject_id` link to any domain object, plus version history and signature state. A share certificate → allotment transaction → board resolution chain is fully navigable.

### 6.5 Rules-as-data
Statutory artifacts — ROC form definitions, compliance deadlines, FEMA pricing methods, valuation rules, stamp-duty rates per state — live in **versioned reference tables**, evaluated by a rules service. Effective-dated so historical computations stay correct after a law change.

---

## 7. Workflow Engine (Module N) — backbone design

The workflow engine is central: most state changes occur inside a workflow run, giving every mutation an auditable origin and approval trail.

- **WorkflowDefinition** — declarative, versioned: ordered/branching **steps**, each with a type (`collect-input`, `generate-document`, `request-signature`, `approval`, `record-transaction`, `trigger-filing`, `external-call`), inputs, guards, and assignees.
- **WorkflowRun** — an instance bound to a legal entity; persists state machine position, collected data, produced artifacts.
- **Step execution** — synchronous steps run inline; long-running steps (e-sign, external filing, payment) suspend the run and resume on a **callback/webhook** or job completion.
- **Branching** driven by entity facts (e.g., *foreign investor present → inject FC-GPR step*; *AIF Cat III → inject tax step*).
- **Idempotency & resumability** — each step is idempotent and checkpointed; safe to retry.

This lets the library of regulated processes (incorporation, priced round, capital call, ESOP grant) be authored as configuration rather than bespoke code.

---

## 8. Integration Architecture

All external systems sit behind an **adapter (anti-corruption) layer** exposing stable internal interfaces, so providers can be swapped and so workflow steps depend on capabilities, not vendors.

| Capability | Provider(s) (integrate, not build) | Pattern |
|---|---|---|
| e-Signature | Aadhaar eSign (eMudhra/NSDL), Leegality, DocuSign | Async; webhook on completion → resume workflow; store tamper-evident PDF. |
| Identity / KYC | DigiLocker, Aadhaar e-KYC, PAN verify, CKYC | Sync verify + cached KYC profile reuse. |
| Incorporation / ROC | MCA21 (assisted; export packages where no API) | Prepare validated package → CS files → capture SRN. |
| Foreign investment | RBI FIRMS/SMF (FC-GPR/FC-TRS/FLA) | Generate filing pack with valuation + CS cert; track status. |
| Payments / escrow | Regulated gateway/escrow partner | Collect subscription monies/drawdowns; reconcile bank statements. |
| Accounting | Tally / Zoho Books / QuickBooks | Export equity & fund transactions. |
| Valuation | Registered valuer / merchant banker (via Services marketplace) | Engagement → report artifact → links to round/grant/FEMA. |
| Demat | NSDL / CDSL / RTA | ISIN, demat status; hand-off. |
| e-Stamp | SHCIL / state e-stamp | Stamp-duty reference on issue/transfer. |

**Resilience:** adapters implement timeouts, retries with backoff, circuit breakers; all outbound calls and inbound webhooks are logged to the audit trail; webhook endpoints verify signatures and are idempotent.

---

## 9. Key Runtime Flows

### 9.1 Incorporate a private limited company (FR-B)
```
Founder → Workflow "Incorporate PvtLtd"
  collect promoters/directors/capital/office
  → run KYC (DigiLocker/PAN) per director
  → generate SPICe+/eMoA/eAoA/AGILE-PRO package (Document svc)
  → request e-sign (DSC/Aadhaar eSign)
  → produce filing-ready pack → assign CS (Services) to file on MCA21
  → on CIN/PAN/TAN captured: create LegalEntity, seed CorporateRecord & registers
  → generate compliance calendar (Compliance) from incorp date/FY
```

### 9.2 Priced round with a foreign investor (FR-E + FR-H FEMA)
```
Founder → Workflow "Priced Round"
  define round/terms → generate term sheet → negotiate/version
  → engage valuer (Valuation, Rule 11UA / FEMA pricing) → store report
  → generate SHA/SSA/board+shareholder resolutions/PAS-4 (Document svc)
  → open round Data Room; invite investors; track engagement
  → collect commitments → e-sign deal docs
  → on closing: record IssuanceTransaction(s) → update CapTableSnapshot
     → generate share certificates → Register of Members entry → stamp duty
  → branch: foreign investor present
     → inject FC-GPR filing task (Compliance) with valuation + CS cert + FIRC/KYC
  → publish investor portal holdings
```

### 9.3 Capital call (FR-J)
```
GP → Workflow "Drawdown N"
  compute pro-rata across CapitalCommitments
  → generate per-LP DrawdownNotices → notify LPs (Notification)
  → track payments (Payments adapter) → update CapitalAccounts (ledger)
  → defaulting-LP handling branch
  → LP portal reflects drawn/remaining
```

### 9.4 e-Sign (cross-cutting, async)
```
Document svc → SignatureRequest → e-Sign adapter (provider)
  workflow step SUSPENDS
  provider webhook (signed) → verify signature → store tamper-evident PDF
  → mark Document signed → RESUME workflow → audit log
```

---

## 10. Security Architecture

- **AuthN:** OIDC/SSO + email-OTP; MFA for privileged roles; DSC registration for directors/CS (FR-A-6). Short-lived JWT access tokens + refresh; sessions in Redis.
- **AuthZ:** RBAC with per-resource scopes (FR-A-2). Authorization enforced in the application command layer **and** at the database via Postgres RLS (defence-in-depth). External professionals get time-boxed, scoped guest grants.
- **Tenant isolation:** mandatory `tenant_id` + RLS; per-tenant CMEK for object storage; cross-tenant access only via explicit consent grants.
- **Encryption:** TLS 1.2+ in transit; AES-256 at rest (CMEK in KMS); secrets in Secret Manager; field-level encryption for high-sensitivity PII (Aadhaar, bank).
- **Document integrity:** signed PDFs retained immutably; hash recorded; e-sign audit trail attached.
- **Privacy / DPDP (NFR-3):** consent capture, purpose limitation, data-principal rights (access/erasure) workflows, configurable retention, breach-notification runbook.
- **Data residency (NFR-2):** all PII/regulated data and backups pinned to an India GCP region.
- **Audit (NFR-4):** every legally significant action emits an immutable, time-stamped `AuditLogEntry` (actor, action, subject, before/after); write-once storage; exportable.
- **App security:** input validation (Pydantic), output encoding, CSRF/CORS controls, rate limiting at gateway, dependency scanning, periodic pen-tests.

---

## 11. Deployment Architecture

```
GitHub → GitHub Actions (WIF, no static keys) → build/test/scan
       → push image to Artifact Registry
       → deploy to Cloud Run (per environment)

Environments: dev → staging → prod  (separate GCP projects)

           ┌──────────── Cloud Run ────────────┐
 Clients → │  api (gateway+modules)  worker(jobs)│
           └─────────┬───────────────┬──────────┘
                     │               │
        Cloud SQL (Postgres HA)   Cloud Tasks
        + read replica            (async queue)
                     │
        GCS (docs, India region, CMEK) · Memorystore (Redis)
        · Secret Manager · Cloud KMS · Cloud Logging/Monitoring/Trace
```

- **Compute:** stateless `api` and `worker` Cloud Run services, autoscaling, multi-zone.
- **Data:** Cloud SQL Postgres with HA + automated backups + PITR; read replica for reporting.
- **Networking:** HTTPS only; serverless VPC connector to private Cloud SQL/Redis; WAF/Cloud Armor at the edge.
- **Secrets/keys:** Secret Manager + KMS; no long-lived credentials (WIF).
- **IaC:** Terraform-managed, reviewed per environment.

---

## 12. Cross-Cutting Concerns

| Concern | Approach |
|---|---|
| Audit & activity | Central append-only log; all mutations via command/workflow layer. |
| Notifications | Email + in-app; SMS/WhatsApp for critical reminders; templated; per-user preferences. |
| Reminders/scheduling | Compliance calendar → scheduled jobs (Cloud Scheduler → Tasks) generate due/overdue notifications with assignee escalation. |
| Observability | Structured JSON logs, request tracing, metrics, alerting on SLOs. |
| Error handling | Typed errors, idempotent retries for integrations, dead-letter for failed jobs. |
| Reporting/export | Async report generation (cap table, ownership, LP capital accounts, compliance health) to PDF/Excel; tenant data export on demand (NFR-8/M-8). |
| Internationalisation | INR/Indian formats; English first; key flows localisable (P2). |
| Feature gating | Module enable/disable per tenant type (startup vs fund) and plan tier. |

---

## 13. Key Design Decisions (ADR summary)

| # | Decision | Why | Trade-off |
|---|---|---|---|
| ADR-1 | Modular monolith over microservices (v1) | Dense relational core; faster delivery; clean seams for later extraction | Single deploy unit; must enforce module boundaries in code. |
| ADR-2 | Event-sourced ledger + materialised snapshots for cap table & capital accounts | Traceability (NFR-7), time-travel, audit | More compute to project; recomputation logic to maintain. |
| ADR-3 | Rules/forms/deadlines as versioned data | Regulation changes without code changes | Needs a rules-authoring + governance process. |
| ADR-4 | Workflow engine as the mutation backbone | Auditable, resumable, config-driven processes | Engine is critical infrastructure; must be robust. |
| ADR-5 | Postgres RLS for tenant isolation (+ app checks) | Defence-in-depth against cross-tenant leakage | RLS adds query complexity. |
| ADR-6 | Integrate specialist providers behind adapters | Speed, compliance, focus | Vendor dependency; adapter maintenance. |
| ADR-7 | Prepare-and-assist filing model | Legal/licensing reality in India | Not fully self-serve for statutory filing; partner network required. |

---

## 14. Mapping to Requirements & Phasing

- **Phase 1 (MVP):** Identity, Entity, CapTable, Document+e-Sign, DataRoom, Compliance (calendar + ROC/FEMA basics), Portal (basic), Workflow engine, Workspace/dashboard — i.e., the relational core + workflow backbone + startup happy path.
- **Phase 2:** FundAdmin (AIF) + SPV, full ESOP, Fundraising compliance/closing automation, Valuation workflows, full Governance, Services marketplace, Managed Admin, CLM, Team, payments/accounting integrations.
- **Phase 3:** Secondaries, AI drafting/review, custom & analytics workflows, public API/webhooks, deeper portal, multi-language.

Non-functional requirements (NFR-1..11) are satisfied by §6 (data/multi-tenancy/ledger), §10 (security/privacy/residency/audit), §11 (availability/deployment), and §12 (cross-cutting).

---

## 15. Risks & Open Issues

1. **Regulatory accuracy & change velocity** — mitigated by rules-as-data + professional review gates; needs ongoing legal maintenance.
2. **Integration availability** (MCA21/FIRMS lack clean APIs) — mitigated by assisted/export model; partner network for filing.
3. **Cross-tenant data sharing** (fund ↔ portco) — consent model must be airtight; privacy/legal sign-off required.
4. **Cap-table/waterfall correctness** — high-stakes math; requires extensive test suites and reconciliation against known scenarios.
5. **Scope breadth (20 modules)** — phased delivery; resist building Phase 2/3 modules before the core is proven.
6. **Servicing vs SaaS positioning** — open product decision (see `REQUIREMENTS.md §10`); affects how much of P/O is built early.

---

*Companion document: see `REQUIREMENTS.md` for full functional/non-functional requirements and the conceptual data model.*

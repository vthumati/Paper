# Paper — Requirements

**An "operating system for corporate legal" for Indian startups and funds.**

Status: **v1.3 (implementation-reconciled)** · Date: 2026-07-15 · Supersedes: v1.2 (2026-07-08), v1.1 (2026-07-03), v1.0 (2026-06-28), Draft v0.1 (2026-06-25)

> v1.0 reconciled the original specification against the working system (backend `apps/api`, frontend `apps/web`); v1.1 adds the cap-table/fund depth batch (fully-diluted view, distribution waterfall, anti-dilution — **145 automated tests passing**). Every functional requirement carries an implementation status; features built beyond the original spec have been added as new FRs (see §11 Changelog).

---

## 1. Vision & Positioning

PaperOS markets itself as *"the operating system for corporate legal"* — a single place where a company's formation, equity, governance, fundraising and legal documents live, stay current, and stay compliant. ([learn.paperos.com](https://learn.paperos.com/cap-table-setup-request))

**Paper** is the India-localised equivalent. It serves two customer types from one platform:

1. **Startups / operating companies** — incorporate, maintain a clean cap table and corporate record, issue equity/ESOPs, raise capital, and stay compliant with MCA/ROC, FEMA/RBI and Income-Tax obligations.
2. **Funds (VC / PE / Angel)** — set up and run a SEBI-registered AIF (Alternative Investment Fund), onboard LPs/contributors, run drawdowns and distributions, track the portfolio, and meet SEBI/FEMA reporting.

The differentiator vs. generic SaaS: regulation is **built in, not bolted on**. The system knows Indian instrument types, statutory forms, filing deadlines and valuation rules, and drives workflows from them.

### Why "PaperOS for India" is not a clone

US-centric platforms (Carta, Pulley, AngelList, PaperOS itself) assume Delaware C-corps, SAFEs, 409A valuations, and Reg D. India has a materially different stack: MCA/SPICe+ incorporation, CCPS/CCD instruments, FEMA/RBI exchange-control filings (FC-GPR/FC-TRS), Rule 11UA valuations by a merchant banker, ESOP rules under the Companies Act, stamp duty per state, and SEBI AIF regulation for funds. Paper's value is encoding *that* stack.

---

## 2. Goals & Non-Goals

### Goals
- Be the single source of truth for a company's/fund's legal + equity record.
- Reduce founder/CFO/fund-admin time on compliance and fundraising paperwork by automating document generation, e-signature, filing prep and reminders.
- Keep the cap table and corporate record continuously accurate and audit-ready (diligence-ready data room on demand).
- Localise every regulated workflow to Indian law.
- *(added v1.0)* Give founders the operating picture — fundraising pipeline, runway/burn, compliance health — not just the legal record.

### Non-Goals (initially)
- We are **not** a registrar/transfer agent (RTA) or a SEBI-registered intermediary; we prepare and assist, we do not file *on behalf of* where law requires a licensed professional. We integrate with / hand off to CS, CA, merchant bankers, and RTAs.
- We do **not** give legal, tax or investment advice. Templates and workflows are tooling; a professional reviews/signs where required.
- We are **not** a payment gateway or escrow ourselves — we integrate with regulated providers.
- We are **not** an accounting/bookkeeping system — the Finance module (§U) tracks runway/burn from summary snapshots; ledgers stay in Tally/Zoho.
- No public securities issuance / listed-company secretarial in v1.

---

## 3. Personas

| Persona | Side | Needs |
|---|---|---|
| **Founder / CEO** | Startup | Incorporate, issue equity, run a round, keep cap table clean, stay compliant without a full-time CS; see pipeline + runway at a glance. |
| **CFO / Finance lead** | Startup | Cap table accuracy, ESOP administration, FEMA/ROC compliance, investor reporting, burn/runway. |
| **Company Secretary (CS)** | Startup/Service | Board/shareholder resolutions, statutory registers, ROC filings, compliance calendar. |
| **Employee / Option holder** | Startup | View grants, vesting, exercise (incl. cashless), tax impact — self-service portal. |
| **Investor (angel/VC)** | Both | Deal docs, data room access, holdings, updates, capital-call notices — scoped read-only portal. |
| **Fund Manager / GP** | Fund | Fund formation, LP onboarding, drawdowns, distributions, portfolio tracking, SEBI reporting. |
| **Fund Admin / Compliance Officer** | Fund | NAV/units, LP statements, SEBI/FEMA filings, KYC/AML. |
| **LP / Contributor** | Fund | Commitment, drawdown notices, capital account, distributions, tax docs. |
| **External professional (CA/CS/Lawyer/Merchant banker)** | Service | Review, e-sign, issue valuation/certificates, collaborate in the data room. |
| **Platform admin / ops** | Internal | Tenant management, servicing workflows, template governance. |

---

## 4. Scope Overview (Module Map)

```
PAPER PLATFORM
├── A. Identity, Tenancy & Access
├── B. Entity Formation, Corporate Record & Startup India   (startup)
├── C. Cap Table & Securities Management                    (startup)
├── D. ESOP / Equity Incentive Administration               (startup)
├── E. Fundraising, Deal Room & Investor CRM                (startup ↔ investor)
├── F. Document Automation & e-Signature                    (shared)
├── G. Governance (Board/Shareholder/Directors)             (startup; fund GP)
├── H. Compliance Engine (MCA/ROC, FEMA, GST/TDS)           (shared)
├── I. Data Room & Diligence                                (shared)
├── J. Fund Administration (AIF)                            (fund)
├── K. Investor / LP / Employee Portal                      (shared)
├── L. Valuations                                           (shared)
├── M. Integrations, Notifications, Alerts, Audit           (platform)
├── N. Workflow Automation Library                          (cross-cutting engine)
├── O. Services Marketplace / Partner Network               (shared)
├── P. Managed Corporate Administration                     (servicing tier)
├── Q. Commercial Contracts / CLM                           (startup)
├── R. Team & HR-Legal                                      (startup)
├── S. SPV / Co-Investment Vehicles                         (fund/investor)
├── T. Workspaces, File Cabinet, Dashboard & Reporting      (platform)
└── U. Finance: Runway / Burn / MIS                         (startup — added v1.0)
```

> Modules N–T were added after a closer pass over the PaperOS knowledge center ([learn.paperos.com](https://learn.paperos.com/), [Corporate Administration](https://learn.paperos.com/corporate-admin)). Module U and the CRM/portal extensions were added in v1.0 from startup-founder gap analysis — capabilities founders need daily that the corporate-legal frame missed.

---

## 5. Functional Requirements

Requirements are tagged **FR-<module>-<n>**. Priority reflects original intent: **M** = MVP, **P2** = phase 2, **P3** = later.

**Implementation status (v1.0):** ✅ implemented & tested · ◐ partially implemented (note says what remains) · ○ not yet implemented. Items marked ⛔ are blocked on external providers/credentials or deployment infrastructure.

### A. Identity, Tenancy & Access

- **FR-A-1 (M)** ✅ Multi-tenant: an organisation (company or fund) is a tenant; users may belong to many tenants with distinct roles.
- **FR-A-2 (M)** ◐ Role-based access control. *Built:* owner/admin/member/viewer roles enforced on every route (app-layer RBAC + per-object context checks). *(v1.4)* **External advisor access** (`AdvisorAccess`, Alembic `e2b4d6c8f0a2`): a company grants a law firm / CA / CS scoped, **cross-tenant** access to a single entity by email — viewer (read-only) or member (acting) — resolved in `deps._entity_role` alongside tenant membership, so the advisor reaches the normal entity workspace at their granted level without any membership in the client's organisation. Advisors get a consolidated **advisor console** (`/advisor`) listing every client entity they can act on. *Remaining:* fine-grained per-document/per-section permissions.
- **FR-A-3 (M)** ◐ Onboarding. *Built:* email+password JWT auth (signup/login/me/refresh) with password policy (min 8), failed-login rate limiting (5 per 5 min, reset on success), and fail-fast boot if the default JWT secret is used outside dev/test; investor/LP/employee access granted by email match without tenant membership, **now gated on email verification** (`email_verified` + `/auth/verify-email` + `PAPER_EMAIL_VERIFICATION_REQUIRED`, dev-off/prod-on) so an unverified pre-registered email cannot inherit another party's access. *Remaining:* OTP/SSO (OIDC) and the transactional-email delivery of the verification token (currently logged). ⛔ partially (SSO/OTP and email transport need providers).
- **FR-A-4 (M)** ○ ⛔ KYC/identity capture (PAN, Aadhaar/DigiLocker, CKYC) — needs live KYC providers.
- **FR-A-5 (P2)** ✅ *(promoted in practice)* Immutable audit log: HTTP middleware records every mutating request (actor, path, result) platform-wide; per-user activity view.
- **FR-A-6 (P2)** ○ ⛔ DSC registration for directors/CS.

### B. Entity Formation, Corporate Record & Startup India

- **FR-B-1 (M)** ◐ Guided incorporation. *Built:* the **incorporation wizard** (Atlas-style, v1.3) — one intake (name options for RUN, capital, registered office, founders with DIN/shares/director flags, validated: ≥2 directors, subscription within authorised capital) generates the SPICe+/eMoA/eAoA filing pack **plus a founder IP assignment per founder** (v1.3) against a pre-registration entity; record the SRN, then the CIN — at which point founder shares are allotted at par, first directors registered and the compliance calendar generated, handing straight into the stage guide. Also the original `incorporate_pvt_ltd` workflow. *Remaining:* KYC/e-sign integration in the pack (⛔ credentials); LLP/OPC-specific branches.
- **FR-B-2 (M)** ◐ Incorporation document generation. *Built:* SPICe+ (summary), eMoA, eAoA templates generated from entity data. *Remaining:* AGILE-PRO, INC-9, DIN/DSC checklists, name-reservation flow.
- **FR-B-3 (M)** ✅ Statutory identifiers: CIN, PAN, incorporation date on the entity (TAN/GSTIN via registrations/tax records).
- **FR-B-4 (M)** ✅ Corporate record: every generated/signed document is linked (polymorphic subject) and surfaced in the file cabinet; registers and cap table derive from the ledger.
- **FR-B-5 (M)** ✅ Statutory registers: Register of Members (derived from the cap-table ledger), Register of Directors/KMP, **Register of Charges** (create/satisfy), **SBO register** (BEN-2 data). ESOP register via grants.
- **FR-B-6 (P2)** ✅ *(promoted — implemented)* **DPIIT / Startup India module**: eligibility checker from entity facts (type, <10-yr age, turnover note), recognition record (DPIIT number/dates), and tax-benefit applications — **80-IAC holiday** and **angel-tax exemption u/s 56(2)(viib)** — gated on recognised status.
- **FR-B-7 (P2)** ○ Entity conversion workflows (LLP → Pvt Ltd; Pvt → Public).
- **FR-B-8 (P2)** ✅ *(promoted — implemented)* Multi-state registrations: GST / Professional Tax / Shops & Establishments / PF / ESIC per state, with numbers and status.

### C. Cap Table & Securities Management

- **FR-C-1 (M)** ✅ Live cap table: as-issued view computed by replaying the full event ledger (issue/transfer/convert/buyback/split/bonus/rights), with cost basis that follows shares; plus a **fully-diluted view** (unexercised option grants, unallocated ESOP pool, outstanding SAFEs/notes as-if-converted at an assumed price or current FMV; unpriceable instruments listed as excluded, not guessed).
- **FR-C-2 (M)** ✅ Indian instruments: Equity, CCPS, CCD, option pool, warrants as security classes; **SAFE / convertible notes as first-class instruments** with valuation cap, discount, MFN flag, and interest accrual (notes); **execution flow** (v1.3) — each instrument carries its paper trail: one-click circular board resolution (passes through the standard resolution machinery), agreement document generated from the recorded terms (re-versioned until signed, immutable after), e-signature via the platform flow, with `board / doc / e-sign` status surfaced on the instrument row.
- **FR-C-3 (M)** ✅ Conversions: class-to-class conversion with configurable ratio (e.g. CCPS→equity at 1.5×); SAFE/note conversion at min(cap price, discounted round price) with accrued interest, preview + convert; **anti-dilution** terms per class (broad-based weighted average / full ratchet with original issue price) and a down-round calculator returning the adjusted conversion price, ratio, and per-holder additional shares.
- **FR-C-4 (M)** ✅ Round modelling: pre/post-money, committed vs target, new-share and dilution computation per round; **scenario modeling** (v1.3) — pro-forma cap table for a *hypothetical* round (new money, pre-money or price, pool top-up created pre-money, SAFEs converting at the scenario price) with per-holder before/after/dilution, side-by-side comparison in the UI, nothing written to the ledger.
- **FR-C-5 (M)** ◐ Liquidation waterfall. *Built:* preference stacks by seniority (pro-rated within a tier when short), participating and non-participating preferred, remainder pro-rata; **exit comparison** (v1.3) — per-holder proceeds across several exit values, showing where the preference stack flips to pro-rata. *Remaining:* the as-converted election for non-participating preferred (take-preference vs convert optimisation).
- **FR-C-6 (M)** ◐ Issuance lifecycle. *Built:* issuance → ledger → Register of Members; share-certificate template; certificate-number field. *Remaining:* board-approval gating on allotment; auto certificate generation per issuance.
- **FR-C-7 (M)** ✅ Corporate actions: transfers (SH-4) with holding validation, buy-backs, **stock splits**, **bonus issues**, and **rights issues** (pro-rata entitlements → subscriptions → close-and-issue), all effective-dated on the ledger with deterministic ordering.
- **FR-C-8 (M)** ◐ Stamp duty. *Built:* transfer stamp duty at the uniform 0.015% of consideration, computed per transfer. *Remaining:* issue-side duty, state-wise rates table, e-stamp reference. ⛔ e-stamp integration.
- **FR-C-9 (P2)** ◐ Demat: ISIN + depository (NSDL/CDSL) + status tracked per security class. *Remaining:* RTA hand-off. ⛔
- **FR-C-10 (M)** ✅ Effective-dated, append-only ledger; positions recomputable as of any date; microsecond-ordered events. *(v1.3)* **Narrative timeline** — every equity event (issuances, transfers, conversions, buy-backs, corporate actions, SAFEs/notes, grants, exercises, valuations, rounds) rendered as a human-readable sentence, newest first, as a Cap Table sub-tab (`GET /entities/{id}/timeline`).
- **FR-C-11 (M — added v1.0)** ✅ **Founder reverse-vesting / restricted stock**: cliff-then-monthly schedule over issued founder shares; unvested shares repurchasable (buy-back at nil) on early exit.
- **FR-C-13 (M — added v1.4, Ledgy gap)** ✅ **Company liquidity windows (buyback / tender)**: the company opens a fixed-price window over a period (`liquidity_events`); shareholders **tender** shares from their portal (`tenders`, validated against holdings); **settlement** buys back every accepted tender at the event price as append-only cap-table `BuybackTransaction`s (skipping any holder who no longer has the shares). Admin sees tender counts and an indicative payout; the portal surfaces open windows across every entity where the user holds shares. *Remaining:* per-tender accept/reject, proration on oversubscription, external-buyer (secondary) settlement.
- **FR-C-12 (M — added v1.0)** ✅ Cap-table **CSV export**, and *(v1.3)* **CSV import** for onboarding an existing cap table: downloadable template, row-by-row validation as a dry run (nothing written), then an atomic apply that creates missing share classes and stakeholders and appends the issuances to the ledger; warns when the ledger already has entries.

### D. ESOP / Equity Incentive Administration

- **FR-D-1 (M)** ◐ Schemes. *Built:* scheme with pool size and pool-limit enforcement on grants; *(v1.4)* **adoption pack** — one-click generation of the statutory documents to adopt a scheme (board resolution, EGM notice with the s.62(1)(b) special resolution, and the ESOP policy); **ESOP overview dashboard** — pool size / granted / available + used %, option states (vested / exercised / exercisable / unvested), grantee count, a pool-composition donut and a top-grants leaderboard (`GET /esop/overview`, read-only). *Remaining:* scheme versioning, SEBI SBEB variants.
- **FR-D-2 (M)** ◐ Grants. *Built:* per-employee grants, cliff + linear monthly vesting, time-based tracking. *(v1.4)* **Three award types** on one vesting model (`grant_type`, Alembic `e1a3c5b7d9f0`): **options** (vest → exercise at strike; perquisite = FMV−strike at exercise), **RSUs** (no strike; vest → settle to shares for no consideration; perquisite = full FMV at settlement, per Sec 17(2) at vesting), and **RSAs** (shares issued upfront at grant, unvested portion subject to repurchase; perquisite = FMV−price at allotment). *Remaining:* grant letters, milestone vesting, acceleration on exit, RSA repurchase-on-exit automation.
- **FR-D-3 (M)** ✅ Employee self-service: portal shows granted/vested/exercised/exercisable, strike, current FMV and unrealised gain; **self-serve exercise requests** (v1.3) — employees request exercise in the portal (validated against vested-minus-exercised-minus-pending), the company approves into a chosen class (the real exercise lands on the ledger, perquisite computed) or rejects; perquisite (FMV − strike) computed on exercise. *(v1.3)* **Vesting projection** — the portal equity view leads with vesting-progress %, a vested/unvested progress bar, the estimated 100%-vesting date, and the next scheduled vest events per grant.
- **FR-D-4 (P2)** ◐ *(largely promoted)* Exercise. *Built:* exercise → cap-table issuance; **cashless exercise** (net shares after withholding to cover strike; gross consumed from grant); *(v1.4)* **exercise windows** — opt-in open/upcoming/closed periods (`exercise_windows`); once an entity defines any, exercise requests are gated to an open window, else unrestricted. *Remaining:* loan-funded and leaver scenarios.
- **FR-D-5 (P2)** ✅ *(promoted — implemented)* Valuation linkage: exercise falls back to the entity's current effective valuation when FMV isn't supplied; UI prefills current FMV.
- **FR-D-6 (P2)** ✅ *(v1.4)* Option-holder buyback / liquidity events — see **FR-C-13** (company-run buyback/tender windows; holders tender vested shares, settlement writes cap-table buybacks).
- **FR-D-7 (M — added v1.4, recurring competitor gap)** ✅ **Share-based-payment expense (Ind AS 102)**: grant-date fair value — Black-Scholes for options (spot = FMV at grant + user-supplied volatility / risk-free rate / expected life / dividend yield), full FMV for RSUs/RSAs — amortised straight-line over the vesting term, aggregated per Indian financial year, with recognised-to-date vs unrecognised totals and an expense-report document. Grants with no FMV at grant date are surfaced as unpriced. *Remaining:* forfeiture true-ups, graded per-tranche curves.

### E. Fundraising, Deal Room & Investor CRM

- **FR-E-1 (M)** ✅ Round workspace: define round (instrument, pre-money, target, price, class), add commitments (soft → signed → funded), close.
- **FR-E-2 (M)** ◐ Term sheets. *Built:* term-sheet generation from round data, document versioning. *Remaining:* negotiated-term tracking/redlines.
- **FR-E-3 (M)** ◐ Round document set. *Built:* SHA (summary), PAS-4, board-resolution templates generated and linked. *Remaining:* SSA; full India-grade legal drafts.
- **FR-E-4 (M)** ◐ Round data room: rooms exist with grants/analytics; per-round auto-scoping remains manual.
- **FR-E-5 (P2)** ◐ Private placement. *Built:* PAS-4 template; **PAS-3 filing obligation auto-created on close** (30-day due date); **Sec 42 offeree guardrail** — offers (SAFEs + commitments) capped at 200 distinct persons per FY, enforced at entry. *Remaining:* separate-bank-account tracking, QIB/ESOP offeree exclusions, full Section 42 pack.
- **FR-E-6 (P2)** ✅ *(promoted — implemented)* Closing mechanics: on close, **outstanding SAFEs/notes convert automatically** at the round price into the round's class (valuation caps priced off the pre-financing cap table; an instrument that can't convert is left outstanding rather than blocking the close), then funded commitments are issued into the cap-table ledger; **FC-GPR FEMA obligation auto-created when any investor is foreign**; investor portal reflects holdings.
- **FR-E-7 (P3)** ◐ *(promoted v1.3)* Secondary sales with ROFR. *Built:* an investor requests a sale from their portal (holding-validated); the company exercises its right of first refusal by choosing the buyer — approval executes a stamp-dutied transfer on the cap-table ledger; reject path; status visible to the seller. *Remaining:* open marketplace / multi-bidder allocation.
- **FR-E-8 (M — added v1.0)** ✅ **Investor CRM / fundraising pipeline**: prospects with stages (contacted → meeting → diligence → term-sheet → committed/passed), firm, check size, notes; pipeline summary (open vs committed value by stage); **one-click conversion of a prospect into a round commitment**; **public funnel link** (v1.3) — one shareable URL per round where prospective investors register interest (rate-limited, unauthenticated) landing directly in the CRM, optionally auto-granting data-room access; admin funnel view joins prospects × data-room engagement × commitments.
- **FR-E-10 (M — added v1.3)** ✅ **PAS-4 private placement offer letter** per commitment (Sec 42 / rule 14(3)): named offeree, shares derived from the round price, generated into Documents.
- **FR-E-11 (P2 — added v1.3)** ✅ **Term sheet scanner**: paste a term sheet and a rules-as-data reviewer flags off-market terms against the India-market standard (liquidation multiples above 1x, participating preferred, full ratchet, long exclusivity, oversized pre-money pools, redemption/put rights, cumulative dividends, personal guarantees, low drag thresholds) with matched snippets and founder-readable explanations; customary terms are confirmed as standard. Deliberately rules-based — explainable and testable; information, not legal advice.
- **FR-E-9 (M — added v1.2)** ✅ **Family & friends investing**: every SAFE/note and round commitment carries an investor kind (friends & family / angel / institutional) shown across fundraising views; F&F investors given an email see their instruments in the investor portal automatically (no explicit grant needed); the Pre-seed stage guide walks founders through it with the Sec 42 guardrail (FR-E-5) enforcing the 200-offeree/FY limit.

### F. Document Automation & e-Signature

- **FR-F-1 (M)** ✅ Template library (~20 India-specific templates): incorporation (SPICe+/eMoA/eAoA), board resolution, share certificate, SHA, PAS-4, term sheet, meeting notice, D&O indemnification, offer letter, IP assignment, NDA, MSA, SOW, fund/SPV docs. *Note:* parameterised merge; clause-level composition remains open.
- **FR-F-2 (M)** ◐ Data merge + versioning. *Built:* entity/round/grant data merged into templates; append-only versions; regenerate blocked after signing; **PDF download for every generated document** (members via Documents; LPs download their own statements/Form 64C from the portal). *Remaining:* redline comparison; richer PDF layouts.
- **FR-F-3 (M)** ◐ e-Signature. *Built:* full signing lifecycle (request → signatories → provider-callback → signed, tamper-lock) with a simulated provider. *Remaining:* ⛔ real Aadhaar eSign (eMudhra/NSDL) / Leegality / DocuSign adapters.
- **FR-F-4 (M)** ✅ Document as first-class object with polymorphic links (round, resolution, meeting, contract, team member, workflow run, director…).
- **FR-F-5 (P2)** ○ Clause library + AI-assisted drafting/review.
- **FR-F-6 (P2)** ○ ⛔ e-stamp/SHCIL and notarisation hand-off.

### G. Governance (Board, Shareholders, Directors)

- **FR-G-1 (M)** ✅ Meetings: board/AGM/EGM with date, venue, quorum; **agenda items**; **notice generation** (agenda + quorum merged into a linked notice document); minutes + held/cancelled status.
- **FR-G-2 (M)** ✅ Resolutions: board/ordinary/special/circular; pass/fail with dates; board-resolution document generation; **MGT-14 filing obligation auto-created when a special/circular resolution passes**; **charter amendment** (v1.3) — one step drafts the MoA/AoA alteration as a special resolution plus a linked document, feeding the same MGT-14 hook on passing.
- **FR-G-3 (M)** ◐ Consents: circular resolutions serve the written-consent path. *Remaining:* formal consent object with per-party sign-off and statutory-validity checks.
- **FR-G-4 (P2)** ✅ *(promoted — implemented)* Director/KMP register: designations (MD/WTD/independent/nominee/CS/CFO), DIN, appointment/resignation with **DIR-12 obligations auto-created** on both events. *Remaining:* disqualification checks.
- **FR-G-5 (P2)** ○ Board portal (pre-reads, voting, action items).
- **FR-G-6 (P2)** ✅ *(promoted — implemented)* D&O indemnification agreement generation per director.

### H. Compliance Engine (MCA/ROC, FEMA/RBI, GST/TDS)

- **FR-H-1 (M)** ✅ Compliance calendar, three generators: **annual ROC** (AOC-4, MGT-7, DIR-3 KYC, DPT-3, ADT-1 from FY end, rules-as-data), **event-based** (PAS-3 on allotment, MGT-14 on special resolution, DIR-12 on director change, FC-GPR on foreign allotment — auto-created by the triggering action), and **recurring** (12× monthly GSTR-3B due the 20th following, 4× quarterly TDS 26Q). All idempotent.
- **FR-H-2 (M)** ◐ Filing prep. *Built:* status lifecycle (due → in-prep → filed → acknowledged) with SRN capture and assignee. *Remaining:* validated filing packages per form. ⛔ MCA21 submission.
- **FR-H-3 (M)** ◐ FEMA. *Built:* FC-GPR obligation auto-created with 30-day due date on foreign allotment. *Remaining:* FC-TRS on transfers to/from non-residents, FLA annual reminder, filing-pack artifacts (valuation + CS cert + FIRC). ⛔ FIRMS portal.
- **FR-H-3a (P2)** ○ ODI / overseas-investment tracking.
- **FR-H-4 (M)** ◐ Reminders. *Built:* **alerts engine** — due-soon/overdue obligations and contract renewals aggregated across a user's entities; sweep converts alerts to in-app notifications (deduped). *Remaining:* ⛔ email/SMS/WhatsApp delivery; scheduled (cron) sweep.
- **FR-H-5 (P2)** ◐ Tax hooks. *Built:* ESOP perquisite computation; 80-IAC and angel-tax exemption tracked in the Startup India module; GST/TDS return calendar. *Remaining:* TDS-deposit tracking tied to exercises; accounting hand-off.
- **FR-H-6 (P2)** ✅ *(promoted — implemented)* Compliance **health score** (filed/total %, overdue count) surfaced per entity; compliance **CSV export**.

### I. Data Room & Diligence

- **FR-I-1 (M)** ◐ Data rooms. *Built:* rooms with folders, per-email access grants with **enforced expiry**, **text watermarking** on every viewed document (room + viewer stamped). *Remaining:* download controls, PDF watermarking.
- **FR-I-2 (M)** ◐ Population: any entity document can be added; auto-populate from the corporate record remains open.
- **FR-I-3 (M)** ✅ Engagement analytics: per-actor, per-document view counts.
- **FR-I-4 (P2)** ◐ *(largely promoted)* **Diligence Q&A**: ask/answer threads per room. *Remaining:* request-list checklists, redaction.
- **FR-I-5 (P2)** ◐ **Diligence readiness engine** (v1.3): 11 rules-as-data checks sweep the entity's own records (founder/team IP assignments, founder vesting, pending signatures, issuances without board approval, ESOP-vs-valuation, pool overruns, overdue filings, director register, expired data-room grants, stakeholder emails) → severity-weighted score + findings with deep links; report saved as a document. *Remaining:* one-click export package of the underlying documents.

### J. Fund Administration (AIF)

- **FR-J-1 (M)** ◐ Fund setup. *Built:* fund profile per entity — SEBI Category I/II/III, structure, target corpus, carry %, hurdle %. *Remaining:* PPM / trust deed / contribution-agreement generation; SEBI registration checklist.
- **FR-J-2 (M)** ◐ LP onboarding. *Built:* LPs with commitments and email linkage (drives the LP portal). *Remaining:* ⛔ KYC/AML; ₹1-crore minimum-commitment validation; FEMA checks for foreign LPs.
- **FR-J-3 (M)** ✅ Commitment register + capital accounts (committed / drawn / remaining / distributed), derived from the drawdown & distribution ledgers.
- **FR-J-4 (M)** ◐ Capital calls. *Built:* pro-rata drawdown notices per LP, payment marking. *Remaining:* defaulting-LP handling.
- **FR-J-5 (M)** ◐ Distributions. *Built:* cumulative European **waterfall** — return of capital → preferred return (hurdle %, simple, accrued per paid drawdown) → 100% GP catch-up → carry split — with the per-tier breakdown stored on each distribution and shown in the Fund tab; net allocated to LPs pro-rata by paid-in capital; **management-fee accrual and charging** (simple annual % on committed or drawn basis; one-click crystallisation into an append-only fee ledger shown per LP in capital accounts). *Remaining:* compounding / tiered-hurdle variants.
- **FR-J-6 (M)** ✅ Portfolio: investments (instrument, amount, ownership %) per fund; SPV positions sweep into portco cap tables (same-tenant).
- **FR-J-7 (M)** ◐ Accounts/statements. *Built:* per-LP capital-account view (portal + API); **fund performance** — DPI/RVPI/TVPI and XIRR computed from the drawdown/distribution ledgers with **portfolio mark-to-market** (unmarked positions held at cost) as NAV, shown to GPs and LPs; **LP capital-account statements** generated as documents that surface automatically in the LP's portal; **angel/direct-investor portfolio summary** (position value at latest FMV, MOIC) in the portal. *Built (cont.):* **unitised NAV** — units at ₹10 par against paid-in capital, per-LP units in capital accounts and statements, NAV per unit with performance. *Remaining:* NAV-priced unit issuance; scheduled statement runs.
- **FR-J-8 (M)** ◐ SEBI periodic reporting. *Built:* **SEBI AIF compliance calendar** — quarterly activity reports (due 15 days after quarter end), annual PPM-audit report and compliance test report generated idempotently into the compliance engine per FY. *Remaining:* ⛔ actual SI-portal filing; grievance log.
- **FR-J-10 (M — added v1.3)** ✅ **Fund deal pipeline** (GP-side CRM): deals with stages sourced → screening → diligence → IC → term sheet → invested/passed; **one-click invest** converts a deal into a portfolio investment (linked, double-invest guarded).
- **FR-J-11 (M — added v1.4, Mantle gap)** ✅ **Schedule of Investments & LP look-through**: a GP-facing **SOI** — per holding cost, fair-value mark, MOIC, unrealised gain and % of NAV, with portfolio totals and a generated SOI statement document; and LP-facing **look-through** in the portal — each LP's pro-rata slice (paid-in share, falling back to commitment share) of every underlying holding at the fund's own marks, so an LP sees *through* their fund position to the companies it exposes them to. Uses the fund's reported marks only — no portfolio-company privacy boundary crossed. *Remaining:* multi-level fund-of-funds look-through (one level today).
- **FR-J-25 (M — added v1.7, Visible gap)** ✅ **DDQ answer bank**: a per-fund due-diligence Q&A repository — LP questionnaire questions answered once and reused, organised by category, seeded from **standard-question presets** (firm, fund terms, track record, SEBI compliance, valuation policy, conflicts, service providers, ESG), duplicate questions rejected, and exportable as a **DDQ Responses document** with category sections (unanswered questions marked "response pending"). `GET/POST /funds/{id}/ddq`, `PUT/DELETE .../{entry_id}`, `POST /funds/{id}/ddq/report`. *Remaining:* per-LP questionnaire instances; mapping an incoming LP DDQ onto bank answers.
- **FR-J-24 (M — added v1.7, Vestberry gap)** ✅ **Internal benchmarking (portfolio medians)**: each portfolio company's latest period side-by-side on the core metrics (revenue, revenue growth %, monthly burn, runway, headcount) **and every custom metric from FR-J-23**, against the **portfolio median** per metric, with above/below markers. Answers "is this company normal *for this portfolio*" without external comps data (which is why external benchmarks stay out of scope). Pure derivation over the monitoring data, no schema. `GET /funds/{id}/benchmarks`. *(extended v1.7, Visible gap)* **Segment comparison** — investments carry a free-text `sector` tag; the benchmark payload adds per-segment cohorts (median per metric + company count per sector, untagged grouped as "—", hidden when only one cohort exists); sector chips on the monitoring table and a segment-medians table under the benchmark table. **Quartiles** *(v1.7 visual batch)* — per-metric distribution stats (min / Q1 / median / Q3 / max / total / reporters) as Q1/Q3 ticks on the range strips and a Distribution table. *Remaining:* vintage cohorts.
- **FR-J-23 (M — added v1.7, Vestberry gap)** ✅ **Custom KPI definitions + ESG presets**: a fund defines its own metrics (label + unit ₹/number/%; key auto-slugged from the label) collected alongside the core KPIs — with one-click **ESG presets** (female headcount %, independent directors %, GHG emissions, energy use, CSR spend — rules-as-data). Values are captured per period on the KPI report (stored as JSON on the period, filtered to defined keys) and flow into monitoring and FR-J-24 benchmarking. Deleting a definition keeps historical values, they just stop being shown. `GET/POST /funds/{id}/kpi-definitions`, `DELETE .../{id}` (409 duplicate key). *Remaining:* custom metrics on portal KPI requests (investee self-reporting); per-metric trend charts.
- **FR-J-22 (M — added v1.7, Vestberry gap)** ✅ **Quarterly LP report pack**: a one-click quarterly report document per fund — fund snapshot (committed / drawn / uncalled / distributed), since-inception **performance** (NAV, NAV per unit, DPI / RVPI / TVPI / XIRR), **activity this period** (capital calls by due date and distributions by date falling in the reporting window, with amounts and carry), the **Schedule of Investments** with totals, and **valuation status** vs the FR-J-15 policy — composed entirely from the existing capital-accounts / performance / SOI / valuation services, amounts lakh/crore-formatted, unaudited-figures disclaimer. The report **surfaces automatically in every LP's portal** statements list (fund-wide, alongside their personal capital-account statements and Form 64C). `POST /funds/{id}/lp-report` (period label + start/end; 400 on inverted period). *Remaining:* per-LP personalised section (their capital account inside the pack); scheduled quarterly runs; PDF branding.
- **FR-J-21 (M — added v1.7, Vestberry gap)** ✅ **Company tear sheets**: a one-pager document per portfolio company generated in one click from the Portfolio table — investment summary (instrument, invested, ownership, reporting contact), **value & MOIC** (cost, fair value, unrealised gain), the **latest valuation** (value, methodology, valuer, independence, as-of — or "fund's own mark" when only a mark exists), the **KPI trend** (last 4 periods, newest first, with runway) and the company's **active signals** from FR-J-20 (or a healthy note) — composed entirely from the monitoring/valuation/signals services, amounts lakh/crore-formatted. Lands in the entity's Documents (PDF-renderable like all documents). `POST /funds/{id}/portfolio/{iid}/tear-sheet`. *Remaining:* custom sections/branding; batch generation for the whole portfolio.
- **FR-J-20 (M — added v1.7, Vestberry gap)** ✅ **Portfolio signals**: rules-based early warning derived from the KPI history and marks — **revenue decline** period-over-period (high severity beyond 20%), **low runway** (< 6 months), **mark below cost** (impairment %), **reporting gone silent** (> 6 months since the last period; "never reported" info) — plus the positive signal, **follow-on candidates** (growing revenue with ≥ 12 months runway, feeding the FR-J-12 reserves decision). Severity roll-ups (high / warn / info / positive / all-clear) and per-company signal rows, worst first. Pure derivation, no schema. `GET /funds/{id}/signals`. *(extended v1.7, Visible gap)* **Metric alerts** — fund-defined thresholds on any tracked metric (core KPIs, growth, runway, or `custom.<key>` definitions): rule = metric + falls-below/rises-above + threshold + severity (high/warn), evaluated on read against each company's latest period; breaches surface as `metric_alert` signals with the rule's severity (unit-aware formatting). `GET/POST/DELETE /funds/{id}/alert-rules` (GET returns the metric catalog shared with benchmarks); "Metric alerts" panel in `PortfolioMonitoring.tsx` (rule chips + add form). *Remaining:* notification digests.
- **FR-J-19 (M — added v1.7, Vestberry gap)** ✅ **KPI reporting requests (investee self-service)**: the GP asks each portfolio company's **reporting contact** (email stored on the investment) for a KPI period; the contact sees the request in **their portal** (plus an in-app notification if they have an account) with due date and overdue flag, submits revenue/cash/burn/headcount, and the GP **accepts** the submission into `PortfolioKPI` (or **reopens** it for resubmission). Request lifecycle pending → submitted → accepted, email-scoped submission, 409 double-submit/accept guards. `POST /funds/{id}/portfolio/{iid}/kpi-requests`, `GET /funds/{id}/kpi-requests`, `POST .../accept|reopen`, portal `POST /portal/kpi-requests/{id}/submit`. *(extended v1.7, Visible gap)* **Recurring schedules + no-login submission**: a per-company **request cadence** (monthly / quarterly) materialised on read — opening the requests list creates the request for the last completed period if missing (idempotent; quarters labelled as Indian-FY quarters, due = period end + 14 days); and every request mints a **secret link token** so the contact can submit **without a Paper account** via a public page (`/submit-kpis/{token}` → `GET/POST /public/kpi-requests/{token}[/submit]`, 404 unknown token, 409 resubmit) — Visible's "frictionless founder experience". `GET /funds/{id}/kpi-schedules`, `PUT/DELETE /funds/{id}/portfolio/{iid}/kpi-schedule`; "Make recurring" + schedule chips + per-request "Copy link" in `PortfolioMonitoring.tsx`. *Remaining:* custom-metric requests (see FR-J-23 *Remaining*).
- **FR-J-18 (M — added v1.6, Carta fund gap)** ✅ **LP self-service — consolidated view + online capital-call notices**: the portal shows a **consolidated LP position across every fund** (committed / drawn / uncalled / distributed / **NAV of the LP's units** via the unitised model / pending-call count) and, per fund, the LP's **capital-call notices** (call no., purpose, due date, amount, paid / pending / **overdue** status) which the LP can **acknowledge** online (idempotent, email-scoped); the GP sees acknowledgement status per notice in the Fund workspace (`drawdown_notices.acknowledged_at`). `POST /portal/notices/{id}/ack`. *Explicitly out of scope (integration-blocked):* money movement — collecting drawdowns / paying distributions via NACH/UPI needs live payment rails.
- **FR-J-17 (M — added v1.6, Carta fund gap; extended v1.7, 4Degrees gaps)** ✅ **Deal-CRM depth**: relationship intelligence on the deal pipeline — per-deal **contacts** (name, role, email) and a dated **activity timeline** (note / meeting / call / email, newest-first, append-only, kind icons), with activities optionally **attributed to a contact**. Derived **relationship strength** (0–100, rules-based: touch frequency + recency over 6 months) per deal and per contact, shown as mini pies. **Deal source** (who referred it) feeds a top-deal-sources chart; **follow-up reminders** (`next_followup_on`) flag overdue deals in the pipeline and surface red in the entity Tasks hub. The pipeline renders as a **kanban board** (stage columns, cards with sector chip, cheque, contact avatars; Board/Table toggle) with a **pipeline analytics** snapshot (deals-by-stage columns w/ counts + value, sector donut, top active deals, top sources). `GET /deals/{id}/crm`, `POST /deals/{id}/contacts|activities`, `PUT /deals/{id}/followup`. *Remaining (integration-blocked, by design):* email/calendar sync, LinkedIn capture, data enrichment; relationship-path mapping across deals.
- **FR-J-16 (M — added v1.6, Carta fund gap)** ✅ **LP-fundraising CRM**: the GP-side pipeline for raising the fund *from* prospective LPs (distinct from the deal pipeline, which deploys capital). Prospects carry firm, kind (institutional / family office / HNI / fund-of-funds), target cheque and a stage (prospect → contacted → meeting → diligence → soft-circled → committed / passed); **converting** a won prospect creates an `LP` with their commitment (idempotent-guarded). A fundraise summary shows committed (actual LP capital) vs **target corpus** with progress, soft-circled and active-pipeline totals, and a per-stage breakdown. `GET /funds/{id}/fundraise`, `POST /funds/{id}/prospects`, `POST /funds/{id}/prospects/{pid}/stage`, `POST /funds/{id}/prospects/{pid}/convert`. *Extended v1.7 (4Degrees gap):* per-prospect **CRM depth** mirroring the deal pipeline — dated activity timeline (`lp_prospect_activities`), derived **relationship strength**, and **follow-up reminders** (`lp_prospects.next_followup_on`; overdue → 🔔 in the pipeline + red Tasks-hub entry, cleared by converting). `GET/POST .../prospects/{pid}/crm|activities`, `PUT .../followup`. *Remaining:* per-prospect documents; email capture.
- **FR-J-15 (M — added v1.6, Carta fund gap)** ✅ **SEBI-compliant independent portfolio valuation**: a fund **valuation policy** (appointed independent valuer + revaluation frequency in months) and per-holding **valuation records** (fair value, as-of, methodology — IPEV market/recent-txn, DCF, NAV, cost — valuer, independence flag, note; append-only history, latest by as-of becomes the holding's mark so NAV/SoI/performance stay in sync). A valuation dashboard flags holdings **stale** against the policy frequency, rolls up valued/independent/stale counts, and generates a `fund_valuation` report document. `PUT /funds/{id}/valuation-policy`, `POST/GET /funds/{id}/portfolio/{iid}/valuations`, `GET /funds/{id}/valuations`, `POST /funds/{id}/valuations/report`. An India-native differentiator (SEBI AIF independent-valuation duty that global tools don't localise). *Remaining:* valuer e-sign/attestation; multi-valuer reconciliation.
- **FR-J-14 (M — added v1.5, Carta fund gap)** ✅ **Fund financial statements** (no GL export): since-inception **statement of operations**, **cash flows**, **assets & liabilities** and a **partners'-capital roll-forward**, derived from the drawdown/distribution/fee ledgers and portfolio marks — designed so **net assets ties to ending partners' capital** by construction (a `balances` check is surfaced). Also generates a `fund_financials` statement document. `GET /funds/{id}/financials`, `POST /funds/{id}/financials/report`. Documented simplifications: cash is a derived plug (no bank ledger), realised gains aren't split from marks, no accrued liabilities; a management view, not audited GAAP. *Explicitly out of scope for now (per product decision):* GL export (Tally/Zoho). No schema change (pure projection).
- **FR-J-13 (M — added v1.5, Carta fund gap)** ✅ **Portfolio-company monitoring**: per-portfolio-company operating KPIs reported per period (revenue, cash, monthly burn, headcount, note; append-only, latest-by-as-of drives the dashboard) with derived **runway** (cash ÷ burn), period-over-period **revenue growth**, and a **low-runway flag** (< 6 months); a fund-level health roll-up (companies reporting, summed latest revenue & cash, count low on runway) and a per-company revenue **trend chart**. `POST/GET /funds/{id}/portfolio/{iid}/kpis`, `GET /funds/{id}/portfolio-monitoring`. *Remaining:* company self-service data requests; multi-metric charts; export.
- **FR-J-12 (M — added v1.5, Carta fund gap)** ✅ **Fund forecasting / portfolio construction**: a per-fund construction model — investable capital (fund size − lifetime management fees − estimated expenses), initial-cheque vs **reserve** split, implied number of initial deals, average entry ownership, projected **gross / net TVPI** and an approximate net IRR, plus year-by-year **deployment pacing** across the investment period — with **plan-vs-actual** read live from the portfolio and LP ledgers (committed vs target, deployed vs initial capital, deals vs plan). Fee % and carry % are read from the Fund so terms stay single-source. All figures are a planning model (documented simplifications: flat fee accrual, hurdle ignored in the carry projection, timing-free IRR). `GET/PUT /funds/{id}/plan`. *(extended v1.7, Visible gap)* **Variance report** — the plan payload adds a row-per-metric plan-vs-actual table with a signed variance %: committed capital, capital deployed to date (planned = even pacing × fund years elapsed since the first `invested_on`), average initial cheque, portfolio companies, gross MOIC (actual = fair value over cost, unmarked positions at cost) and net TVPI (actual from fund performance; blank until capital is paid in). Rendered under Plan-vs-actual in `FundForecast.tsx`. *Remaining:* stage-based reserve strategies; scenario/sensitivity comparison.
- **FR-J-9 (P2)** ✅ *(promoted — implemented)* SPV / fund-of-one — see Module S.
- **FR-J-10 (P2)** ○ Co-investment side-letter tracking.

### K. Investor / LP / Employee Portal

- **FR-K-1 (M)** ✅ Investor dashboard: per-user portal (matched by email, **no tenant membership required**) showing company holdings (own stakeholder only), fund capital accounts, documents shared via data rooms, and a portfolio summary (companies, funds, total invested, total committed). *(v1.4)* **Value hero** — a big current marked-value figure over a **value-over-time line chart** with 3M/6M/1Y/All range toggles, reconstructed from each company's FMV history (holdings × FMV at each valuation date, held at cost before the first valuation; equity-holdings series only, labelled distinct from the all-in portfolio stat).
- **FR-K-2 (M — extended v1.7, Visible gap)** ✅ **Structured investor updates**: Visible-style update composer with period label, highlights / lowlights / asks sections alongside the narrative body; a **live metrics snapshot** (FR-K-8 metrics) is frozen onto the update at publish time; **draft → published lifecycle** (drafts editable, invisible in the portal, published updates immutable); and **per-viewer engagement tracking** — invited investors open updates in their portal ("Read" records a view) and the company sees viewers × open counts per update.
- **FR-K-3 (M — added v1.4, Ledgy gap)** ✅ **Employee equity views**: an **equity hero** framing the portal ESOP section — today's value (vested units at intrinsic value for options, full FMV for RSUs/RSAs), max potential value of the whole grant, a vested/unvested bar, and next-vest / fully-vested dates; and a **per-grant detail** (`GET /portal/grants/{id}/detail`, own-grant only) with three value stats, a **vesting-status segment bar** (exercised/settled · vested · unvested) and a **vesting timeline** (start → past events collapsed → a *today* marker → upcoming events → fully vested) from a computed month-by-month schedule.
- **FR-K-3 (P2)** ◐ Self-service documents: shared data-room documents listed in the portal (expiry-enforced). *Remaining:* statements/certificates/tax-doc downloads.
- **FR-K-4 (P2)** ◐ Q&A: data-room diligence Q&A. *Remaining:* general secure messaging.
- **FR-K-5 (M — added v1.0)** ✅ **Employee equity portal**: employees see their ESOP grants — granted/vested/exercised/exercisable, strike, current FMV, **unrealised gain** — plus summary counters, matched by email.
- **FR-K-6 (M — added v1.3)** ✅ **Investor consents (reserved matters)**: the company requests electronic consent on a resolution from every portal-invited investor; investors approve/reject in their portal (email-authorised, decide-once); the company sees the live tally. Pairs with SHA reserved-matter clauses.
- **FR-K-7 (M — added v1.3)** ✅ **LP tax pack**: Form 64C generated per LP from the FY's distribution ledger (auto-visible in the LP portal beside statements) and fund-level Form 64D, per section 115UB / rule 12CB.
- **FR-K-8 (M — added v1.4, trica gap)** ✅ **Periodic investor report**: a live metrics snapshot assembled from the entity's own records (shares issued, stakeholders, capital raised, current FMV, open rounds, options granted, cash/burn/runway, overdue compliance) combined with founder-entered highlights into a generated report document, shareable via a data room. `GET /investor-report/preview` for the metrics; `POST /investor-reports` to generate.

### L. Valuations

- **FR-L-1 (M)** ◐ Valuation records: reports with method, valuer, FMV, valuation date, validity; linked from ESOP; valuer engageable via the Services marketplace. *Remaining:* structured request→deliverable workflow.
- **FR-L-2 (M)** ✅ Methods tracked: Rule 11UA (issue pricing), FEMA pricing, fair value (ESOP); **current-FMV resolution** = latest final, effective, unexpired report as of a date. *(v1.3)* **FMV-over-time chart** — registered valuations plotted as a line series, overlaid with saved indicative per-share estimates.
- **FR-L-3 (P2)** ✅ *(v1.3, Eqvista gap analysis)* **Self-serve indicative valuation**: scorecard (Bill Payne weighted factors over a benchmark pre-money), VC method (exit ÷ target multiple − planned raise), and DCF-lite (discounted projection cash flows + terminal value) — any subset blended by custom weights, translated to a per-share value on the fully-diluted count, **smartfilled** from the entity's financial snapshots, saved as reusable scenarios, and exported as an indicative-valuation workpaper document. Indicative only (disclaimer travels with every result); not a registered-valuer report. `ValuationEstimate` model, Alembic `d4f6a8c0b2e4`.
- **FR-L-4 (P2)** ◐ Expiry: validity honoured in current-FMV resolution. *Remaining:* proactive refresh reminders.

### M. Integrations, Notifications, Alerts, Audit (Platform)

- **FR-M-1 (M)** ○ ⛔ Real e-sign providers (Aadhaar eSign, Leegality, DocuSign) — lifecycle built, adapters pending credentials.
- **FR-M-2 (M)** ○ ⛔ KYC providers (DigiLocker, Aadhaar e-KYC, PAN verify, CKYC).
- **FR-M-3 (M)** ◐ Notifications. *Built:* in-app notifications (bell, unread counts, mark-read), event-driven (FC-GPR alerts, calendar generation) + alert sweep. *Remaining:* ⛔ email/SMS/WhatsApp channels.
- **FR-M-4 (P2)** ○ ⛔ Payments/escrow + bank reconciliation.
- **FR-M-5 (P2)** ○ ⛔ Accounting export (Tally/Zoho/QuickBooks).
- **FR-M-6 (P2)** ○ ⛔ Government portals (MCA21, FIRMS, GST, Income-Tax).
- **FR-M-7 (P2)** ○ ⛔ RTA / NSDL / CDSL.
- **FR-M-8 (M)** ◐ Audit + export. *Built:* platform-wide immutable audit middleware; CSV exports (cap table, compliance). *Remaining:* full tenant data export.
- **FR-M-9 (P3)** ○ Public API / webhooks.
- **FR-M-10 (M — added v1.0)** ✅ **Alerts / reminder engine**: aggregates due-soon and overdue compliance obligations + contract renewals across all entities a user can access; home-page alert feed; sweep-to-notifications with dedupe. *(Delivery channels ⛔ per FR-M-3.)*

### N. Workflow Automation Library

- **FR-N-1 (M)** ✅ Workflow = declarative multi-step process (collect-input, external-call, generate-document, request-signature, record-transaction, trigger-filing, approval, notify); typed steps perform real side-effects (document generation, signature requests) whose outputs flow into the run context.
- **FR-N-2 (M)** ◐ Library: `priced_round` and `incorporate_pvt_ltd` seeded; catalogue endpoint. *Remaining:* broader curated library.
- **FR-N-3 (M)** ✅ Run state machine: persisted runs/steps, one active step, suspend/resume, assignee roles, auditable.
- **FR-N-4 (P2)** ✅ *(promoted — implemented)* Conditional branching on run context (e.g. `foreign_investor` → inject FC-GPR step), evaluated lazily so mid-run data drives the path.
- **FR-N-5 (P2)** ○ Org-authored custom workflows.
- **FR-N-6 (P3)** ○ Workflow analytics.

### O. Services Marketplace / Partner Network

- **FR-O-1 (M)** ✅ Provider directory: CS / CA / lawyer / registered valuer / RTA / fund admin / **registered-office & virtual-CFO providers** (v1.3), category-filterable, with **platform verification** — anyone may register a listing but only platform-verified providers can be engaged (admin allowlist via `PAPER_PLATFORM_ADMIN_EMAILS`).
- **FR-O-2 (M)** ◐ Engagements: entity-scoped engagement with scope/SOW, status lifecycle (requested → accepted → in-progress → delivered → closed), deliverable-document link. *Remaining:* scoped provider access into the tenant's data room.
- **FR-O-3 (P2)** ○ ⛔ In-platform billing/escrow; ratings.
- **FR-O-4 (P2)** ○ Partner multi-client workspace.

### P. Managed Corporate Administration

- **FR-P-1..P-3 (P2)** ◐ Tooling built (subscription state, engagement/deliverable links); the managed operations themselves are a service-delivery motion.
- **FR-P-4 (P2)** ✅ Quarterly touchpoint meetings logged (date, attendee, summary).
- **FR-P-5 (P2)** ✅ Audit engagements: corporate audit / pre-diligence / clean-up with status and findings.
- **FR-P-6 (P2)** ◐ Tiering: basic/growth/scale tiers recorded, one subscription per entity. *Remaining:* pricing logic.

### Q. Commercial Contracts / CLM

- **FR-Q-1 (P2)** ✅ Counterparty registry: customers/vendors/partners with contacts.
- **FR-Q-2 (P2)** ◐ Contract lifecycle. *Built:* contracts with type/value/dates/status; MSA/SOW/NDA document generation linked to the contract. *Remaining:* redlining; e-sign wiring to contracts.
- **FR-Q-3 (P2)** ✅ Renewal & obligation tracking: renewal dates, days-to-renewal, overdue flags, renewals-due query; feeds the alerts engine.
- **FR-Q-4 (P3)** ○ AI clause extraction.

### R. Team & HR-Legal

- **FR-R-1 (P2)** ✅ Team registry: employees/contractors/advisors with title, status, join/exit dates.
- **FR-R-2 (P2)** ✅ HR documents: offer letter, IP assignment, NDA generated per member (guarded to HR templates).
- **FR-R-3 (P2)** ◐ Onboarding bundle: one click creates an EMPLOYEE cap-table stakeholder (**ESOP-eligible immediately**) + generates the 3 HR docs. *Remaining:* PF/ESIC/PT checklist step.
- **FR-R-4 (P3)** ✅ Joiner/leaver: onboarding links the stakeholder; **offboarding** (v1.3) exits the member and automatically lapses unvested options back to the scheme pool (vesting frozen at the leaving date).

### S. SPV / Co-Investment Vehicles

- **FR-S-1 (P2)** ◐ SPV creation: sponsor, target company, structure, optional portco link (same-tenant; cross-tenant consent model deferred); **subscription agreements** (v1.3) auto-generated per co-investor on commitment (re-versioned on revision, immutable once signed) and downloadable from the backer's portal. *Remaining:* SPV operating-agreement generation.
- **FR-S-2 (P2)** ✅ Co-investor register (commitment/contribution/paid) + **sweep**: the SPV's combined position issues into the portco cap table as a single ENTITY stakeholder.
- **FR-S-3 (P2)** ◐ **Syndicate subscription flow**: the lead invites backers by email; the deal appears in their investor portal (terms, target, sponsor, status) where they commit — minimum ticket enforced — and the lead marks money received (`invited → committed → funded`). *Remaining:* distributions back to co-investors.
- **FR-S-4 (P2)** ✅ **Deal economics**: carry % + minimum ticket per SPV; saving terms provisions the fund profile on the SPV entity (carry mirrored, zero hurdle/management fee) so the capital-call and distribution-waterfall machinery applies to the vehicle.
- **FR-S-5 (P3)** ○ Multi-SPV roll-up reporting.

### T. Workspaces, File Cabinet, Dashboard & Reporting

- **FR-T-1 (M)** ◐ Workspaces: users hold many tenants/entities and switch freely; cross-entity **alert feed** on the home page. *Remaining:* consolidated cross-entity dashboard.
- **FR-T-2 (M)** ✅ File cabinet: every document across all modules in one searchable list (title search, source/subject shown).
- **FR-T-3 (M)** ✅ Unified per-entity dashboard: cap table, fundraising, compliance (incl. overdue), ESOP, governance, documents, data rooms — plus a fund block for fund entities. Default landing tab. *(v1.3)* **Visual overview** — class-ownership and share-usage **donut charts** (dependency-free SVG), a general-details panel with **authorized vs issued vs available** shares (authorized derived from the incorporation charter when present), a **valuation status card** (active with FMV/method/dates, or action-needed when missing/expired), and a **quick-actions row** deep-linking to issue shares / grant options / raise / pass a resolution. *(v1.4)* **Tasks hub** — a Home-group tab aggregating everything actionable for the entity (pending e-signatures, open option-exercise requests, overdue compliance filings, outstanding investor consents), ranked with overdue first, each row deep-linking to the tab that resolves it.
- **FR-T-9 (M)** ✅ *(v1.4, Mantle gap analysis)* **Cap-table ownership bar** — a 100%-stacked horizontal share-class bar above the holdings table; **avatar initials chips** on stakeholder/holder rows; **document card grid** with per-type tag chips replacing the flat document list.
- **FR-T-4 (P2)** ✅ *(promoted — implemented)* Tax-records vault: GST/TDS/Form-16/ITR entries with period, reference, amount.
- **FR-T-5 (P2)** ◐ Exports. *Built:* CSV for cap table and compliance. *Remaining:* PDF/Excel report pack, LP capital-account statements.
- **FR-T-6 (P3)** ○ Configurable dashboards.
- **FR-T-7 (M)** ✅ *(added v1.2)* **Stage-based guided workspace**: every company carries a lifecycle stage (Inception → Pre-seed → Seed → Series rounds → Pre-IPO) that drives progressive disclosure — only stage-relevant tabs and feature parts are surfaced (e.g. SAFEs at Pre-seed, priced rounds/data rooms at Seed, anti-dilution and waterfalls at Series, demat at Pre-IPO), with an "All features" escape hatch so nothing is ever unreachable. Stages are guides, not gates: **any stage can be skipped or revisited** from the picker. Each stage ships a **"what to do now" checklist** (rules-as-data) whose items are auto-checked from real data and deep-link to the right screen; the stage is user-set with an **auto-suggestion inferred from the company's data** (e.g. a SAFE suggests Pre-seed, a closed priced round suggests Series).
- **FR-T-8 (M)** ✅ *(added v1.2)* **Grouped navigation**: features are organised into a two-level menu — Home · Ownership (cap table/ESOP/valuations) · Fundraise (rounds & SAFEs/data room/investors) · Governance (board/compliance/registers/Startup India) · Operations (team/contracts/finance/documents/files/workflows) · Partners (marketplace/managed admin), plus Fund/SPV groups for fund entities — replacing the flat ~20-tab row. The active group shows its sub-tabs; single-tab groups open directly.

### U. Finance: Runway / Burn / MIS *(module added v1.0)*

The founder's daily operating picture — deliberately summary-level (not bookkeeping; see Non-Goals).

- **FR-U-1 (M)** ✅ Monthly financial snapshots: cash balance, monthly burn, revenue — manual entry, upserted by month.
- **FR-U-2 (M)** ✅ **Runway computation**: latest cash ÷ average burn over the trailing 3 months, with a low-runway (<6 months) visual alert; history table.
- **FR-U-3 (P2)** ○ ⛔ Auto-sync balances/burn from banking or accounting (Tally/Zoho) integrations.
- **FR-U-4 (P3)** ○ MRR/metrics pack feeding investor updates.

---

## 6. Conceptual Data Model

This is a **conceptual / logical** model — the core entities and how they relate, not a physical schema. It is technology-agnostic; a relational store fits most of it, with a document store for files. Cardinality shown as `1—n` (one-to-many) or `n—n` (many-to-many).

### 6.1 Modelling principles

1. **Party model.** People and organisations are modelled once as `Party` (subtype `Person` / `OrgParty`). A party plays many **roles** via `PartyRole`. *(v1.0 implementation note: the build uses a pragmatic simplification — per-entity `Stakeholder` rows plus **email-matching** for portal access (investor/LP/employee). The Party/PartyRole normalisation is a target-state refactor; see §6.11.)*
2. **Multi-tenant.** Every business record is owned by a `Tenant`; `LegalEntity` is the regulated subject; a tenant may hold many entities.
3. **Effective-dated & immutable.** Cap-table and capital-account state are derived from append-only **transaction ledgers**; positions are projections. *(Implemented: issuance/transfer/conversion/buyback/corporate-action/rights events replayed chronologically with cost-basis-follows-shares.)*
4. **Document as first-class, polymorphic link.** A `Document` attaches to any subject via `subject_type/subject_id`. *(Implemented.)*
5. **Workflow-driven.** Mutations of record happen inside a `WorkflowRun` or an audited API action. *(Implemented: workflow engine + platform-wide audit middleware.)*

### 6.2 Core / shared entities

| Entity | Key attributes | Key relationships |
|---|---|---|
| **Tenant** | id, name, type (company/fund/firm), plan tier, status | 1—n Workspace, LegalEntity, Membership |
| **Workspace** | id, tenant_id, name | groups LegalEntity (n—n); user views |
| **User** | id, email, auth identity, status | n—n Tenant via Membership; 1—1 Party (optional) |
| **Membership** | user_id, tenant_id, role, scopes | links User↔Tenant; carries RBAC |
| **Role / Permission** | role, permission, resource scope | drives FR-A-2 access checks |
| **Party** | id, kind (person/org), legal name | supertype of Person/OrgParty *(target state)* |
| **Person** | party_id, PAN, Aadhaar ref, DIN, DOB, nationality | 1—1 KYCProfile; plays PartyRoles |
| **OrgParty** | party_id, CIN/registration no., country | external orgs (investors, vendors) |
| **PartyRole** | party_id, entity_id, role, period | a party's role in a given entity |
| **KYCProfile** | party_id, docs, verification status, CKYC ref | reused across onboarding/FEMA |
| **Address** | id, lines, state, PIN, type | registered office, party address |
| **Document** | id, type, title, status, subject_type, subject_id, file ref | n—1 DocumentTemplate; 1—n DocumentVersion, SignatureRequest |
| **DocumentVersion** | document_id, version, file, author, redline | version history |
| **DocumentTemplate** | id, type, jurisdiction, clauses, version | 1—n Document |
| **AuditLogEntry** | actor, action, subject, timestamp, diff | immutable trail (NFR-4) |
| **Notification** | recipient, channel, type, payload, read_at | reminders/updates |

### 6.3 Entity formation & corporate record

| Entity | Key attributes | Relationships |
|---|---|---|
| **LegalEntity** | id, tenant_id, type (PvtLtd/LLP/OPC/Trust/Fund/SPV), name, CIN, PAN, TAN, GSTIN, incorp date, FY | hub of the model |
| **CorporateRecord** | entity_id | aggregates registers, charters, resolutions, certs |
| **StatutoryRegister** | entity_id, type (Members/Directors/Charges/SBO/ESOP), rows | derived from transactions |
| **DirectorOfficer** | entity_id, party_id, designation, DIN, appointed/resigned | governance |
| **Registration** | entity_id, kind (GST/PT/Shops/PF/ESIC), state, number, status | FR-B-8 multi-state |
| **SignificantBeneficialOwner** *(v1.0)* | entity_id, name, PAN, %, nature | SBO register (BEN-2) |
| **Charge** *(v1.0)* | entity_id, holder, amount, type, created_on, satisfied | Register of Charges |
| **StartupRecognition** *(v1.0)* | entity_id, status, DPIIT no., recognised_on, valid_until | one per entity |
| **TaxBenefitApplication** *(v1.0)* | entity_id, type (80-IAC / 56(2)(viib)), status, reference | gated on recognition |

### 6.4 Cap table & securities

| Entity | Key attributes | Relationships |
|---|---|---|
| **SecurityClass** | entity_id, kind, par value, **pref_multiple, participating, seniority** | 1—n ledger events |
| **Stakeholder** | entity_id, name, type (Founder/Investor/Employee/Entity), email | email drives portal matching |
| **IssuanceTransaction** | entity_id, class, stakeholder, qty, price, date, certificate_no | append-only ledger event |
| **TransferTransaction** *(v1.0)* | class, from/to stakeholder, qty, price, date, **stamp_duty** | SH-4 secondary movement |
| **ConversionEvent** | stakeholder, from/to class, from/to qty, date | CCPS/SAFE→equity |
| **BuybackTransaction** *(v1.0)* | class, stakeholder, qty, price, date | cancellation; also founder repurchase |
| **CorporateAction** *(v1.0)* | class, type (split/bonus), numerator:denominator, date | class-wide, applied in replay |
| **RightsIssue / RightsSubscription** *(v1.0)* | class, ratio, price, record date, status; per-holder take-up | close → issuances |
| **ConvertibleInstrument** *(v1.0)* | investor, type (SAFE/note), principal, cap, discount, MFN, interest, status | converts at min(cap price, discounted round price) + interest |
| **FounderVesting** *(v1.0)* | stakeholder, class, total shares, cliff/total months, start, repurchased | reverse-vesting; repurchase→buyback |
| **DematRecord** *(v1.0)* | class, ISIN, depository (NSDL/CDSL), status | FR-C-9 |
| **CapTableSnapshot** | entity_id, as-of, positions | projection (computed, not stored) |
| **Round** | entity_id, name, instrument, pre-money, target, price, class, status | 1—n Commitment |
| **Commitment** | round_id, investor, amount, shares, is_foreign, status | funded → issued on close |

### 6.5 ESOP

| Entity | Key attributes | Relationships |
|---|---|---|
| **ESOPScheme** | entity_id, pool size | pool-limit enforced |
| **Grant** | scheme, stakeholder, qty, strike, grant date, cliff/total months | vesting computed |
| **ExerciseTransaction** | grant, qty (gross), FMV, strike, perquisite, **net_shares, cashless** | feeds IssuanceTransaction |

### 6.6 Fundraising CRM & governance

| Entity | Key attributes | Relationships |
|---|---|---|
| **ProspectInvestor** *(v1.0)* | entity_id, name, firm, stage, check size, round_id, commitment_id | pipeline; converts to Commitment |
| **Meeting** | entity_id, type, date, quorum, minutes, **notice_document_id** | 1—n Resolution, **AgendaItem** |
| **AgendaItem** *(v1.0)* | meeting_id, order, title | merged into notice |
| **Resolution** | entity/meeting, type, text, status, passed date, document_id | special/circular → MGT-14 obligation |

### 6.7 Compliance, data room, valuation

| Entity | Key attributes | Relationships |
|---|---|---|
| **ComplianceObligation** | entity_id, form, title, category (ROC/FEMA/GST/TAX), period, due date, status, SRN, assignee | annual + event-based + recurring |
| **DataRoom / DataRoomItem / AccessGrant** | room, items→documents, per-email grants with **expiry** | watermarked views |
| **DataRoomQuestion** *(v1.0)* | room, asker, question, answer, answered_by | diligence Q&A |
| **EngagementLog** | room, actor, document, action | view analytics |
| **ValuationReport** | entity_id, method (11UA/FEMA/FV), FMV, valuation date, valid_until, status | current-FMV resolution |

### 6.8 Fund administration (AIF) & SPV

| Entity | Key attributes | Relationships |
|---|---|---|
| **Fund** | entity_id, SEBI category, structure, corpus, carry %, hurdle % | 1—n LP |
| **LP** | fund_id, name, **email** (portal match), commitment | capital account derived |
| **CapitalCall / DrawdownNotice** | call no., pct; per-LP amount, paid | pro-rata |
| **Distribution / LPDistribution** | gross, kind, **carry amount**; per-LP allocation | pro-rata by paid-in |
| **PortfolioInvestment** | fund_id, company, instrument, amount, ownership % | portfolio |
| **FundPlan** *(v1.5)* | fund_id (1—1), fund size, life/investment-period yrs, expenses, reserve %, avg cheque, avg entry post-money, projected gross MOIC | construction/forecast inputs; all outputs derived |
| **PortfolioKPI** *(v1.5)* | investment_id, fund_id, period_label, as_of, revenue, cash, monthly_burn, headcount | append-only per-period ops KPIs; runway/growth derived |
| **PortfolioValuation** *(v1.6)* | investment_id, fund_id, as_of, value, methodology, valuer, is_independent | append-only; latest updates the holding mark. Fund gains valuer_name + valuation_frequency_months (policy) |
| **LPProspect** *(v1.6)* | fund_id, name, firm, kind, stage, target_commitment, lp_id | fund-raising pipeline; converting creates an LP |
| **DealContact / DealActivity** *(v1.6)* | deal_id; name/role/email · kind/body/occurred_on | deal-CRM relationship intelligence + activity timeline |
| **KPIRequest** *(v1.7)* | investment_id, fund_id, period_label, as_of, due_date, contact_email, status, submitted values, kpi_id | investee self-reporting; PortfolioInvestment gains contact_email |
| **KPIDefinition** *(v1.7)* | fund_id, key (unique per fund), label, unit (inr/number/pct) | fund-defined custom metrics incl. ESG presets; values stored as JSON (`custom`) on PortfolioKPI |
| **SPV / CoInvestor / SPVInvestment** | sponsor, target, portco link; commitments; sweep into portco ledger | single-deal vehicle |

### 6.9 Workflow, services, CLM, team, platform

| Entity | Key attributes | Relationships |
|---|---|---|
| **WorkflowDefinition / Run / StepInstance** | key, version, typed steps, conditions; run context; step status/output | engine backbone |
| **ServiceProvider / ServiceEngagement** | category; entity-scoped engagement, status, deliverable doc | marketplace |
| **AdminSubscription / TouchpointMeeting / AuditEngagement** | tier; meetings; audits with findings | managed admin |
| **Counterparty / Contract** | kind; type, value, dates, renewal, status, document | CLM + renewal alerts |
| **TeamMember** | entity_id, name, type, status, **stakeholder_id** | onboarding→ESOP eligibility |
| **TaxRecord** | entity_id, type, period, reference, amount | tax vault |
| **InvestorAccess / InvestorUpdate** *(v1.0)* | entity_id, email, stakeholder link; updates | portal access & comms |
| **FinancialSnapshot** *(v1.0)* | entity_id, month, cash, burn, revenue | runway projection |

### 6.10 Relationship spine (textual ER)

```
Tenant 1─n LegalEntity ── hub
   │
   ├─ Cap-table ledger: Issuance │ Transfer │ Conversion │ Buyback │ CorporateAction │ RightsIssue
   │        └── replayed chronologically ──> positions / waterfall / CSV     (cost basis follows shares)
   ├─ ConvertibleInstrument ──(min(cap, discount) + interest)──> IssuanceTransaction
   ├─ ESOPScheme 1─n Grant ──exercise (incl. cashless)──> IssuanceTransaction (net shares)
   ├─ FounderVesting ──repurchase unvested──> BuybackTransaction
   ├─ Round 1─n Commitment ──close──> Issuances + PAS-3 + (foreign? FC-GPR) obligations
   │        ProspectInvestor ──convert──> Commitment
   ├─ Meeting 1─n AgendaItem; Resolution ──pass(special)──> MGT-14 obligation
   ├─ DirectorOfficer ──appoint/resign──> DIR-12 obligations
   ├─ ComplianceObligation ──> alerts engine ──sweep──> Notifications
   └─ Fund 1─n LP ──> CapitalCall/Distribution ledgers ──> capital accounts ──> LP portal

Stakeholder.email / LP.email / InvestorAccess.email ──matches──> User ──> /portal (scoped read-only)
Document (polymorphic subject) ── attaches to every object above; File cabinet lists all
Audit middleware ── records every mutation ; WorkflowRun ── orchestrates guided processes
```

### 6.11 As-built deviations (to reconcile in a future refactor)

1. **Stakeholder vs Party**: no normalised Party/PartyRole yet; identity across entities is by email match. Acceptable at current scale; revisit if a person's records must merge across tenants.
2. **Holding / ShareCertificate / TermSheet / Consent / FilingTask** are not distinct tables — holdings are projections, certificates/term sheets are Documents, consents are circular Resolutions, filing state lives on ComplianceObligation.
3. **CapTableSnapshot** is computed on demand (never persisted) — simpler and always consistent; persist only if performance demands.
4. **Cross-tenant fund↔portco linkage** is restricted to same-tenant pending a consent model (open question §10.5).

---

## 7. Non-Functional Requirements

- **NFR-1 Security**: encryption at rest/in transit; tenant isolation; least-privilege RBAC; secrets management; pen-testing. *(Status: app-layer RBAC + object-scoped access checks implemented and tested, including negative tests per module; Postgres RLS, encryption config and pen-tests pend deployment.)*
- **NFR-2 Data residency**: India region for regulated/PII data (DPDP Act 2023). *(Pends deployment.)*
- **NFR-3 Privacy/Compliance**: DPDP consent, data-principal rights, retention. *(Pends deployment.)*
- **NFR-4 Auditability**: immutable, time-stamped trail for every legally significant action. *(✅ platform-wide audit middleware; microsecond-ordered, effective-dated ledgers.)*
- **NFR-5 Availability**: 99.9% target; RPO/RTO; backups + DR. *(Pends deployment.)*
- **NFR-6 Performance**: responsive at startup scale (≤ thousands of stakeholders/LPs). *(Event-replay projection is O(events); fine at this scale — snapshot persistence is the escape hatch.)*
- **NFR-7 Accuracy & traceability**: every number traces to a ledger event — no mutable balances. *(✅ implemented; money quantised to paise, share prices to 4 dp.)*
- **NFR-8 Usability**: founder-friendly guided flows; expert mode for CS/CA. *(◐ working UI for every module; guided polish ongoing.)*
- **NFR-9 Localisation**: INR/Indian formats; English first; Indian languages P2. *(◐)*
- **NFR-10 Template governance**: versioned templates, "tooling not advice" disclaimers, professional review gates. *(◐ templates versioned in code; governance process open.)*
- **NFR-11 Scalability/Multi-tenancy**: clean tenant separation; consent-based cross-tenant sharing. *(◐ app-layer isolation tested; RLS pending Postgres.)*
- **NFR-12 Schema evolution** *(added v1.0)*: versioned migrations (Alembic) required before production. *(✅ scaffolded 2026-06-28: baseline migration verified at 67-table parity; dev `create_all` now gated behind `PAPER_AUTO_CREATE_TABLES`; prod runs `alembic upgrade head`.)*
- **NFR-13 Uniform IST clock** *(added v1.2)*: ✅ every recorded time and "today" across the system is **IST (UTC+05:30)** via a single platform clock (`app/clock.py` — `now_ist`/`today_ist`), independent of the host timezone (dev boxes vary; Cloud Run runs UTC). Applies to audit timestamps, ledger event dates, compliance due-date comparisons, vesting/valuation as-of dates, contract renewals, fund drawdown/distribution dates and pref accrual. Sole exception: JWT `exp`/`iat` stay UTC (epoch-based per RFC 7519).

---

## 8. Key India-Specific Regulatory Anchors (build-in checklist)

| Area | Indian instrument / form / rule | Module | Status |
|---|---|---|---|
| Incorporation | SPICe+, eMoA/eAoA, AGILE-PRO, INC-9 (MCA21) | B | ◐ (SPICe+/eMoA/eAoA templates) |
| Annual ROC | AOC-4, MGT-7, DIR-3 KYC, ADT-1, DPT-3 | H | ✅ calendar |
| Event-based ROC *(v1.0)* | **PAS-3** (allotment), **MGT-14** (special resolution), **DIR-12** (director change) | E, G, H | ✅ auto-created |
| GST / TDS *(v1.0)* | **GSTR-3B** monthly, **TDS 26Q** quarterly | H | ✅ calendar |
| Securities | CCPS, CCD, iSAFE/SAFE, notes, warrants, SH-4, PAS-4 | C, E | ✅ |
| Registers | Members, Directors/KMP, **Charges**, **SBO (BEN-2)** | B, G | ✅ |
| Private placement | Section 42, PAS-4, separate bank a/c, PAS-3 | E | ◐ |
| Foreign investment | **FC-GPR** (✅ auto on close), FC-TRS, FLA, FIRMS/SMF | H | ◐ |
| Valuation | Rule 11UA, FEMA pricing, ESOP fair value | L | ✅ tracked |
| Startup benefits | **DPIIT recognition, 80-IAC, 56(2)(viib)** | B | ✅ |
| ESOP | Perquisite tax (FMV−strike), cashless exercise | D | ✅ computed |
| Stamp duty | Transfer duty 0.015% (uniform) | C | ◐ (state-wise + issue-side pending) |
| Demat | ISIN, NSDL/CDSL tracking | C | ◐ |
| Funds | SEBI AIF Cat I/II/III, carry, capital accounts | J | ◐ |
| Data protection | DPDP Act 2023 | NFR | pends deployment |

> All statutory specifics must be validated with current law and reviewed by qualified CS/CA/legal counsel before production use; thresholds and forms change.

---

## 9. Phasing & Implementation Status

**As built (v1.0):** the original Phase 1 *and* Phase 2 scopes are functionally delivered, plus the v1.0 additions (CRM, Finance/runway, founder vesting, employee portal, alerts, registers, DPIIT, corporate actions, rights issues, SAFE/note lifecycle, Q&A/watermarking, CSV exports) and the v1.1 depth items (fully-diluted cap table, fund distribution waterfall with hurdle + GP catch-up, anti-dilution). Backend: FastAPI + SQLAlchemy, **145 tests**. Frontend: React/Vite SPA covering every module (adaptive per-entity tabbed workspace — companies and funds see different tab sets — plus the investor/employee portal, activity log and alert feed).

**Phase 3 — productionisation & integrations (current frontier):**
1. **Deployment**: Postgres + RLS → Cloud SQL/Cloud Run/WIF per `DEPLOYMENT.md` *(Alembic baseline is done; the Postgres provisioning + RLS verification remain deferred by decision)*.
2. **Real integrations** (all ⛔ on credentials): Aadhaar eSign/Leegality, DigiLocker/KYC, payments/escrow, MCA21, RBI FIRMS, NSDL/CDSL, Tally/Zoho, email/SMS delivery.
3. **Depth backlog** (buildable, prioritised): ~~fully-diluted view~~ ✅ · ~~anti-dilution formulas~~ ✅ · ~~fund waterfall (hurdle/catch-up)~~ ✅ · as-converted waterfall election · state-wise stamp duty table · management-fee accrual · NAV/units + LP statements · formal consents · board portal · PDF report pack · auto data-room population · acceleration/leaver ESOP rules · ~~frontend test suite~~ ✅.
4. **Original Phase-3 items**: secondaries marketplace, AI drafting/review, custom workflows, public API, multi-language.

---

## 10. Open Questions / Decisions

1. **Servicing model** — *open.* Hybrid recommended (self-serve + CS/CA marketplace); marketplace + managed-admin tooling is built either way.
2. **Filing posture** — **decided: prepare-and-assist.** The system creates obligations, prepares data and tracks SRNs; licensed professionals file. Revisit per-portal APIs later.
3. **First vertical** — **resolved by build: both.** Startup and fund sides are live in one codebase; go-to-market sequencing remains a commercial call.
4. **Build vs partner for integrations** — **decided: partner/integrate.** Lifecycle logic is built in-house; provider adapters pend credentials.
5. **Cross-tenant fund↔portco linkage** — *open.* Interim: same-tenant only (enforced in SPV). Needs a consent/data-sharing design.
6. **Pricing tiers** — *open.* Managed-admin tiers (basic/growth/scale) exist as fields; packaging undefined.
7. **Party-model refactor** *(new)* — *open.* When to normalise Stakeholder/email-matching into Party/PartyRole (§6.11.1).
8. **Reminder delivery** *(new)* — *open.* Which channel first (email vs WhatsApp) once a provider is chosen; scheduled sweep cadence.

---

## 11. Changelog

**v1.7 (2026-07-20)** — portfolio intelligence (Vestberry competitive gap analysis, fund side):
- **Visible visual batch (fund + startup side)** ✅ — from a visual analysis of visible.vc product screenshots: (1) **dual delta pills on stat tiles** (`Stat` gains `deltas`) — fund header NAV/TVPI/DPI/RVPI show ▲/▼ vs-last-quarter / vs-last-year from the performance series (since-inception fallback for young funds), and monitoring's revenue total shows vs-prior-period; (2) **benchmark quartiles** (clears FR-J-24 *Remaining: quartiles*) — `portfolio_benchmarks` adds per-metric `stats` (min/Q1/median/Q3/max/total/reporters, `statistics.quantiles` inclusive), rendered as dotted Q1/Q3 ticks on the range strips + a Distribution table; (3) **on-screen tear sheet** — `TearSheet.tsx` panel per portfolio row (Avatar header band, invested/FV/MOIC/ownership/%-of-NAV/runway tiles, revenue & growth combo chart, latest-period line incl. custom metrics, active signals; document generator kept); (4) new **`ComboChart`** component (bars + right-axis % line, dependency-free SVG); (5) **stage summary rails + stage-tinted dots** on the LP-fundraise pipeline (per-stage target + count chips) and the startup investor funnel (per-stage value + count from the pipeline summary); (6) **update live preview** — the FR-K-2 composer renders the update as investors will see it (sections + metric chips, "frozen at publish" note). Backend change is (2) only.
- **FR-J-25 (M — added v1.7, Visible gap) — Visible #5 — DDQ answer bank (fund side)** ✅ — new `DDQEntry` {fund, category, question (409 duplicate per fund), answer} (Alembic `c5d6e7f8a9b0`): a per-fund due-diligence Q&A repository — answer LP questionnaire questions once, reuse everywhere — with **10 standard-question presets** (rules-as-data: firm, fund terms, track record, SEBI compliance, valuation policy, conflicts, service providers, ESG) and a generated **DDQ Responses document** (`ddq` template, category sections, unanswered marked "response pending"). `GET/POST /funds/{id}/ddq`, `PUT/DELETE .../{entry_id}`, `POST /funds/{id}/ddq/report`. `FundDDQ.tsx` card on the LP-fundraise sub-tab (grouped Q&A, answered counter, inline answer editor, preset buttons). 3 tests (`test_ddq.py`). *Remaining:* per-LP questionnaire instances; import an LP's DDQ and map questions to bank answers.
- **Visible #4 — portfolio segments + variance report (FR-J-24 / FR-J-12 extended, fund side)** ✅ — `portfolio_investments.sector` free-text segment tag (Alembic `b4c5d6e7f8a9`; add-investment form input, chips on the monitoring table): `portfolio_benchmarks` adds per-sector **cohort medians** (company count + median per metric, hidden with a single cohort) rendered as a segment-comparison table; and `compute_plan` gains a **variance** block — plan vs live ledgers per metric (committed, deployed-to-date vs even pacing since first investment, avg cheque, deal count, gross MOIC at fair-value-over-cost, net TVPI) with signed variance %, rendered as a table in `FundForecast.tsx`. 3 tests (`test_segments_variance.py`).
- **Visible #3 — scheduled KPI requests + no-login submission (FR-J-19 extended, fund side)** ✅ — new `KPIRequestSchedule` (one per investment, monthly/quarterly) + `kpi_requests.token` unique (Alembic `a3b4c5d6e7f8`). `ensure_scheduled_requests` materialises the last completed period's request on read of the requests list (idempotent by period label; Indian-FY quarter labels; due = period end + 14 days; skips companies without a reporting contact — `PUT .../kpi-schedule` 400s until one is set). Every request now carries a secret token: public page `/submit-kpis/{token}` + unauthenticated `GET/POST /public/kpi-requests/{token}[/submit]` let the contact report without an account (shared `submit_request_values` with the portal path). Frontend: "Make recurring" + schedule chips in the request panel, "Copy link" on pending requests, new `SubmitKpis.tsx` public page. 3 tests (`test_kpi_schedules.py`).
- **Visible #2 — metric alerts (FR-J-20 extended, fund side)** ✅ — new `MetricAlertRule` {fund, metric, lt/gt comparator, threshold, high/warn severity} (Alembic `f2a3b4c5d6e7`); evaluated inside `portfolio_signals` against each company's latest period over the shared metric catalog (`metric_options` — 5 core + `custom.<key>` definitions, now also feeding benchmarks); breaches emit `metric_alert` signals with the rule's severity and unit-aware text. `GET/POST/DELETE /funds/{id}/alert-rules`; "Metric alerts" panel (rule chips + metric/condition/threshold/severity form) in `PortfolioMonitoring.tsx`. 3 tests (`test_metric_alerts.py`).
- **Visible #1 — structured investor updates (FR-K-2 extended, Visible.vc gap analysis, startup side)** ✅ — `investor_updates` gains period label, highlights/lowlights/asks sections, a frozen **metrics snapshot** (the FR-K-8 live metrics, JSON-sanitised) stamped at publish, and a **draft → published lifecycle** (`PUT /investor-updates/{id}` edits drafts only, `POST /investor-updates/{id}/publish`, 409 on published); new `investor_update_views` — `POST /portal/updates/{id}/view` (invited-investor-scoped) counts repeat opens per viewer, and the admin list returns per-update viewer/open engagement (Alembic `e1f2a3b4c5d6`). Frontend: structured composer with Publish / Save-draft / edit-draft in `Investors.tsx` + status chips, section rows, metric chips and 👁 viewers·opens per update; portal updates become expandable "Read" cards (view recorded on open) with sections + metric chips. 3 tests (`test_investor_updates.py`).
- **4Degrees functional batch (relationship intelligence, FR-J-16/17 extended)** ✅ — (1) **LP-fundraise CRM depth**: `LPProspectActivity` + `lp_prospects.next_followup_on` (Alembic `d0e1f2a3b4c5`) — per-prospect activity timeline, relationship strength and follow-up reminders in `FundRaise.tsx`, overdue → 🔔 + red `lp_followup` Tasks-hub entry (cleared by converting); (2) **stale-deal triggers**: `fund_deals.stage_changed_at` (stamped on stage moves, created_at fallback) — "stale Nd" badge on board/table past `STALE_DEAL_DAYS=45` + amber `deal_stale` Tasks-hub entry; (3) **firm network directory**: `GET /funds/{id}/network` — deal contacts + LP prospects deduped by email into one roster (links, max strength, last touch), searchable "who do we know at X" `FundNetwork.tsx` card on the Deal pipeline sub-tab; (4) **deals CSV import**: `POST /funds/{id}/deals/import` (validate/apply, template endpoint) + import panel on the pipeline. `StrengthPie` extracted to a shared component. 6 tests (`test_fundraise_crm.py`, `test_network_and_import.py`).
- **4Degrees batch (deal-CRM intelligence, FR-J-17 extended)** ✅ — from a visual analysis of 4degrees.ai (relationship-intelligence CRM): **kanban deal board** (stage columns, cards w/ sector chip, cheque, contact avatars; Board/Table toggle) + **pipeline analytics** (deals-by-stage `ColumnChart`, sector donut, top active deals, top deal sources — client-side over the deals list); **relationship strength** 0–100 (route-level derivation: 15/touch to 60 + recency 40 fading over 183 days) per deal and per contact w/ conic-gradient mini pies; **activity→contact attribution** (`deal_activities.contact_id`, validated per deal) and kind icons; **deal source** + **follow-up reminders** (`fund_deals.source`, `fund_deals.next_followup_on` — Alembic `c9d0e1f2a3b4`; overdue → 🔔 in pipeline + red Tasks-hub entry). 3 tests (`test_deal_intelligence.py`). Skipped as integration-blocked: email/calendar capture, LinkedIn extension, data enrichment, Salesforce sync.
- **Vestberry visual batch (fund side)** ✅ — from a visual analysis of vestberry.com product screenshots: (1) the fund summary header rebuilt as a **stat-tile grid with sparklines** (Committed / Drawn / Uncalled / Distributed / NAV / TVPI / DPI / RVPI / XIRR / NAV-per-unit; trends fed by a new pure-derivation `GET /funds/{id}/performance-series` — NAV/DPI/RVPI/TVPI at each ledger-event date, positions valued at the latest mark or valuation dated on or before each point; 2 tests `test_performance_series.py`); (2) monitoring table gains a **0–10 risk-score chip** (severity-weighted from FR-J-20 signals), company **avatar chips** and a **stale-reporting tint** on the latest period (> 6 months); (3) signals table rows carry full-row **severity tints** (attention-list style); (4) **portfolio revenue overlay** — all companies on one multi-series line chart; (5) benchmark **range strips** — min–median–max per metric with a marker per company; (6) new `ColumnChart` component — **stacked waterfall columns** per distribution (RoC / pref / LP profit / GP carry). New components: `Sparkline` (also available on `Stat` via `spark`), `ColumnChart`. Skipped by design: left-rail nav, AI assistant (env-blocked), FX registry (INR-native), report-customisation dropdowns.
- **FR-J-23 Custom KPI definitions + ESG presets** ✅ — new `KPIDefinition` + `portfolio_kpis.custom` JSON (Alembic `b8c9d0e1f2a3`). `services/fund.py`: ESG_KPI_PRESETS rules-as-data, create (slug key from label, presets pass their key; 409 dup) / list / delete; `add_kpi` filters custom values to defined keys; `_kpi_view` exposes `custom`. Frontend: "Custom metrics" panel in `PortfolioMonitoring.tsx` (definition chips w/ remove, add form, one-click ESG preset buttons) and per-definition inputs on the Report KPIs form. 3 tests (`test_custom_kpis.py`, incl. FR-J-24).
- **FR-J-24 Internal benchmarking** ✅ — `services/fund.py::portfolio_benchmarks` (companies × core+custom metrics from each latest period, `statistics.median` per metric); `GET /funds/{id}/benchmarks`; benchmark table with ▲/▼-vs-median markers and a median footer row in `PortfolioMonitoring.tsx`. Pure derivation.
- **FR-J-22 Quarterly LP report pack** ✅ — `lp_report` document template + `POST /funds/{id}/lp-report` (period label + start/end) composing fund snapshot / performance / period activity (new `services/fund.py::period_activity` — calls by due date, distributions by date, created-date fallback) / SOI / valuation status; surfaces fund-wide in every LP's portal statements (portal statements query gains an OR arm on subject_type `lp_report` + subject_id fund). "Quarterly LP report" button on Capital accounts (defaults to the current quarter, FY-quarter label derived from the end date). No schema change. 3 tests (`test_lp_report.py`).
- **FR-J-21 Company tear sheets** ✅ — `tear_sheet` document template + `POST /funds/{id}/portfolio/{iid}/tear-sheet` composing investment / value & MOIC / latest valuation / KPI trend (last 4, newest first) / active signals from the existing monitoring, valuation and signals services (amounts via `_inr`); "Tear sheet" button per row in the Fund Portfolio table. No schema change. 3 tests (`test_tear_sheet.py`).
- **FR-J-20 Portfolio signals** ✅ — `services/fund.py::portfolio_signals` (rules: revenue decline w/ 20% high threshold, runway < 6 mo, mark below cost, silent > 183 days, follow-on = growth + runway ≥ 12 mo; amounts in signal text formatted lakh/crore via `_inr`); `GET /funds/{id}/signals`; `features/FundSignals.tsx` (severity tiles + worst-first signal table, healthy empty state) at the top of the Portfolio sub-tab. No schema change. 3 tests (`test_portfolio_signals.py`).
- **FR-J-19 KPI reporting requests** ✅ — new `KPIRequest` + `portfolio_investments.contact_email` (Alembic `a7b8c9d0e1f2`). GP requests a period from the company's reporting contact (in-app notification via the existing `notify` service); the contact submits from their portal (email-scoped, 409 on double-submit); GP accepts into `PortfolioKPI` (linking `kpi_id`) or reopens for resubmission; overdue flags against the due date. Frontend: request form + requests table (status/submitted-values/Accept/Reopen) in `PortfolioMonitoring.tsx`; "KPI requests from your investors" card with submit form in `Portal.tsx`. 3 tests (`test_kpi_requests.py`). Next per the Vestberry review: signals (#2), tear sheets (#3).

**v1.6 (2026-07-20)** — Carta fund gaps #4–#7:
- **App-wide money-format sweep + deep-linkable Fund sub-tabs** (presentation-only): the remaining ~60 raw `₹{...}` interpolations across 21 files (Portal, Fundraising, CapTable(+Advanced), ESOP, SPV, scenario/valuation tools, registers, pipeline, Invest page …) routed through `fmtMoney` (lakh/crore grouping; per-share prices now ≤2dp — the dashboard FMV test updated accordingly); the Fund workspace honours `?tab=fund&sub=<key>` deep links (command palette / shared URLs).
- **Fund workspace QA pass** (presentation-only, after the batch): the Fund tab's 13 stacked sections reorganised into **six sub-tabs** (Capital & LPs · LP fundraise · Portfolio · Deal pipeline · Plan & forecast · Financials) following the CapTableHub pattern, with the fund summary card always visible above; all legacy raw `₹{...}` interpolation in Fund/DealPipeline routed through `fmtMoney`/`fmtInt` (lakh/crore grouping); drawdown-notice table gained a header; portfolio/capital-accounts empties now use `EmptyState`; success toasts wired on the remaining fund actions. No backend changes.
- **FR-J-18 LP self-service** ✅ — `drawdown_notices.acknowledged_at` (Alembic `f6a7b8c9d0e1`); portal payload gains `lp_summary` (consolidated cross-fund LP position incl. NAV of units) and per-fund `capital_calls` (notices w/ purpose, due date, overdue flag); `POST /portal/notices/{id}/ack` (email-scoped, idempotent); GP capital-calls table shows acknowledgement. Frontend: `Portal.tsx` LP-position tile row + notices table with Acknowledge; `Fund.tsx` ack badges. 3 tests (`test_lp_selfservice.py`). Money movement (NACH/UPI) explicitly excluded — integration-blocked.
- **FR-J-17 Deal-CRM depth** ✅ — new `DealContact` + `DealActivity` (Alembic `e5f6a7b8c9d0`): per-deal contacts and a dated activity timeline on the existing deal pipeline. Routes `GET /deals/{id}/crm`, `POST /deals/{id}/contacts`, `POST /deals/{id}/activities`. Frontend: expandable per-deal CRM panel in `features/DealPipeline.tsx` (contacts list + add, activity timeline + log). 3 tests (`test_deal_crm.py`).
- **FR-J-16 LP-fundraising CRM** ✅ — new `LPProspect` (Alembic `d4e5f6a7b8c9`): a GP-side pipeline for raising the fund from prospective LPs, with stages and convert-to-LP; `services/fund.py::add_prospect/set_prospect_stage/convert_prospect_to_lp/fundraise_summary`; routes under `/funds/{id}/prospects` + `/funds/{id}/fundraise`. Frontend `features/FundRaise.tsx` (summary tiles, progress-to-corpus bar, add-prospect form, pipeline table with stage select + convert) in the Fund workspace. 3 tests (`test_lp_prospects.py`). (Frontend api method names namespaced `addLpProspect` etc. to avoid clashing with the startup investor-funnel methods.)
- **FR-J-15 SEBI-compliant independent portfolio valuation** ✅ — new `PortfolioValuation` (append-only per-holding valuations; Alembic `c3d4e5f6a7b8`, which also adds `funds.valuer_name` + `funds.valuation_frequency_months`). `services/fund.py`: `set_valuation_policy`, `record_valuation` (latest by as-of rolls into `PortfolioInvestment.current_value`, keeping NAV/SoI/perf in sync), `valuation_summary` (staleness vs policy frequency + valued/independent/stale roll-ups); new `fund_valuation` document template. Routes `PUT /funds/{id}/valuation-policy`, `POST/GET /funds/{id}/portfolio/{iid}/valuations`, `GET /funds/{id}/valuations`, `POST /funds/{id}/valuations/report`. Frontend `features/FundValuations.tsx` (policy editor, roll-up tiles, per-holding table with methodology/valuer/independent + stale badges, per-holding value form, report) mounted in the Fund workspace. 3 tests (`test_portfolio_valuations.py`). The India-native item where Paper exceeds Carta. (Remaining Carta gaps: subsequent-close equalisation, LP/deal-CRM depth, deeper LP self-service / money movement.)

**v1.5 (2026-07-20)** — VC/fund depth (Carta competitive gap analysis, fund side):
- **FR-J-12 Fund forecasting / portfolio construction** ✅ — new `FundPlan` (one per fund, Alembic `a1b2c3d4e5f6`; dev picks it up via `create_all`). Backend `services/fund.py::compute_plan` derives investable capital, initial-vs-reserve split, #deals, avg entry ownership, projected gross/net TVPI + approx net IRR, and year-by-year deployment pacing, with plan-vs-actual from the live portfolio/LP ledgers; `GET/PUT /funds/{id}/plan`. Frontend `features/FundForecast.tsx` (editable model + Stat tiles + pacing bars + plan-vs-actual progress) mounted in the Fund workspace. 7 new tests (`test_fund_plan.py`). Fee/carry read from the Fund (single source).
- **FR-J-13 Portfolio-company monitoring** ✅ — new `PortfolioKPI` (append-only per-period ops KPIs per portfolio company, Alembic `b2c3d4e5f6a7`). Backend `services/fund.py::portfolio_monitoring` computes runway (cash ÷ burn), period-over-period revenue growth, low-runway flag (< 6 mo) and a fund-level roll-up; `POST/GET /funds/{id}/portfolio/{iid}/kpis`, `GET /funds/{id}/portfolio-monitoring`. Frontend `features/PortfolioMonitoring.tsx` (roll-up Stat tiles + KPI-report form + company table with growth ▲/▼ & runway badge + revenue trend via `LineChart`) in the Fund workspace. 3 new tests (`test_portfolio_kpis.py`).
- **FR-J-14 Fund financial statements** ✅ — `services/fund.py::fund_financials` derives a since-inception statement of operations, cash flows, assets & liabilities and partners'-capital roll-forward from the existing ledgers + marks, tying out (net assets == ending partners' capital, `balances` flag); new `fund_financials` document template; `GET /funds/{id}/financials`, `POST /funds/{id}/financials/report`. Frontend `features/FundFinancials.tsx` (four statement tables + ✓balances badge + generate-statement) in the Fund workspace. No schema change. 3 new tests (`test_fund_financials.py`). Per product decision, **GL export (Tally/Zoho) intentionally excluded**.
- Prioritised Carta fund-side items #1, #2 and #3 all done. (Remaining from the Carta review, not yet scheduled: subsequent-close equalisation, LP/deal CRM depth, SEBI-compliant independent valuation, deeper LP self-service / money movement.)

**v1.4 (2026-07-16)** — full-round review remediation (security + quality, no new features):
- **Email verification gate** (FR-A-3, SEC review H-1): email-matched cross-tenant access (investor portal, LP statements, advisor console, data-room documents) now resolves only for a user who has proven ownership of their email. `users.email_verified` + `email_verification_token` (Alembic `f4d6c8e0a2b4`), `POST /auth/verify-email`, and a `PAPER_EMAIL_VERIFICATION_REQUIRED` flag (off in dev so signups verify immediately — mirrors `auto_create_tables`; on in prod). Enforced in `deps._entity_role` (advisor branch) and a `require_verified_email` dependency on all `/portal*` + advisor routes.
- **Admin-only access delegation** (SEC review M-1): granting/revoking external advisor access and granting investor-portal access now require owner/admin (new `deps.require_admin`), not any write role — a member-level advisor can no longer create a durable second foothold.
- **Readable API errors**: the web client now formats FastAPI 422 validation `detail` lists into `field: message` instead of rendering `[object Object]`.
- **In-app prompt dialog**: `window.prompt()` (blocked in embedded browsers/webviews — the incorporation "Mark filed"/"Record CIN", data-room answer, and other flows dead-ended) replaced by a promise-based in-app modal (`uiPrompt`), across 8 files.
- **Quality/consistency**: single-source `services/fy.py` for Indian-FY math (label format unified to `FY{end}` across ESOP expense / compliance / fund tax statements; removed 4 re-implementations of the Apr–Mar rule); frontend `lib/format.ts` (`fmtMoney`/`fmtInt`) with the two disagreeing private helpers consolidated and the portal value hero migrated; shared `useResource` hook added and Portal's private `useGuard` re-implementation removed. Dead-code sweep: removed `MembershipOut` schema, 6 unused API-client methods, 4 unused imports. 266 backend tests, 7 frontend tests.
- **UI modernization pass** (presentation-only, all in `styles.css` + small components): modern **design tokens** — system-ui body font (replacing Calibri), a shadow/radius scale, soft card elevation, global transitions, branded focus rings, and modern data tables (uppercase muted headers, horizontal rules only, `tabular-nums`, row hover); **responsive top bar** (wraps + hides tagline on small screens, fixing a real mobile horizontal-scroll bug); **toast notifications** (`components/Toast.tsx`, fired via a `useGuard(fn, successMsg)` chokepoint); **skeleton loaders** (`components/Skeleton.tsx`, in the portal); and sharper **KPI stat tiles**. **Dark mode**: full token-based theming (`--heading`/`--panel` split so brand surfaces stay green while heading text and panels flip), an OS-preference default with a persisted top-bar toggle (`data-theme` on `<html>`), verified readable across headings, tables, badges, popovers and inputs. **Consistency rollout**: the shared `EmptyState` (icon + title + hint) replaced hand-rolled "None yet." text across ~15 more feature/page surfaces (Governance, Fundraising, Workflows, Fund, SPV, Admin, Advisors, Compliance, Contracts, Services, Valuations, cap-table timeline, Activity, Entities, Tenants, Advisor console, portal updates); a **branded, centered login screen**; and **success toasts** wired into the core create flows (cap-table issue/add, valuations, fundraising round/commitment/term-sheet/close, governance, team).

**v1.3 (2026-07-14)** — investor & fund depth (FR-J-5, FR-J-7):
- **Fund performance**: DPI / RVPI / TVPI and money-weighted **XIRR** from the drawdown/distribution ledgers; **portfolio mark-to-market** (`current_value`/`marked_on`, Alembic `e6b8d0f2a4c6`) drives NAV; shown in the Fund tab and to every LP in the portal.
- **LP capital-account statements**: generated documents (new `lp_statement` template) per LP, auto-visible in the LP's portal.
- **Management-fee accrual**: `mgmt_fee_pct` + `fee_basis` (committed/drawn, Alembic `f8c0e2a4b6d8`), simple annual accrual surfaced with performance.
- **Angel portfolio summary**: portal totals gain position value at latest FMV and **MOIC**; per-company value shown.
- **Fee charging** (append-only fee ledger per LP, Alembic `a9d1f3b5c7e9`), **unitised NAV** (₹10-par units, NAV/unit), **fund deal pipeline** (new FR-J-10, Alembic `b0e2a4c6d8f0`), and the **SEBI AIF compliance calendar** (FR-J-8 ◐).
- **Form 64C/64D** LP tax pack (new FR-K-7), **investor consents on resolutions** (new FR-K-6), and **secondary sales with ROFR** (FR-E-7 ◐) — consents + secondary requests via Alembic `c1f3b5d7e9a1`.
- **PDF rendering** for all generated documents incl. portal downloads (FR-F-2) and **cap-table CSV import** with dry-run validation (FR-C-12).
- **Security hardening batch** (whole-code review): provider verification gate (FR-O-1, Alembic `d3a5c7e9f1b3`), bounds on money/percentage inputs (negative principals, carry ≥ 100% etc. now 422), fee charging clamped to accrued-to-date, signup rate limiting, spreadsheet-formula neutralisation on CSV exports, import size/row caps.
- **Incorporation wizard** (FR-B-1, Atlas gap analysis): intake → SPICe+/eMoA/eAoA pack → SRN → CIN with automatic allotment, director register and compliance calendar (Alembic `e5c7a9b1d3f5`); marketplace gains registered-office and virtual-CFO categories.
- **Carta gap batch**: scenario modeling (FR-C-4 ✅), employee self-serve exercise requests (FR-D-3, Alembic `f7d9b1c3e5a7`), waterfall exit comparison (FR-C-5). 191 backend tests.
- **Sydecar gap batch** (2026-07-15): **syndicate subscription flow** (FR-S-3 ◐) — invite co-investors by email, deal appears in their portal, portal commitments with minimum-ticket enforcement, `invited → committed → funded` lifecycle; **SPV deal economics** (new FR-S-4 ✅) — carry % + minimum ticket, terms provision the fund profile on the SPV entity; co-investor SPV positions and updates in the investor portal with portfolio aggregation. Alembic `a8f0c2d4e6b8`; 195 backend tests.
- **Pulley gap batch** (2026-07-15): **term sheet scanner** (new FR-E-11 ✅) — rules-based off-market-term detection with snippets and India-standard explanations; **SAFE execution flow** (FR-C-2) — board-approval circular resolution, agreement generation from recorded terms, in-platform e-sign, per-instrument `board / doc / e-sign` status dashboard. Alembic `c2e4a6b8d0f2`; 208 backend tests.
- **UI polish batch** (2026-07-15, presentation-only): Fundraising and Cap Table tabs became sub-tab hubs (rounds/modeler/scanner/SAFEs/pipeline; holdings/transactions/rights) replacing long stacked scrolls; scenario modeler shows red ▼ / green ▲ ownership-change chips per holder; generated documents preview as a serif "paper sheet" instead of a code block; instrument execution renders as a three-step progress stepper; finding severities are colour-coded.
- **UI polish batch 2** (2026-07-15): **Ctrl/⌘-K command palette** — jump to any entity, any tab of the current workspace (via new `?tab=` deep links), or search the entity's documents; **document generation redesigned** — template placeholders become individual form fields with a live paper-sheet preview and a missing-fields notice (templates now expose their body via the API); cap-table exports consolidated into an **Actions ▾** menu; **visual identity refresh** — warm cream background, deep-green accent, serif display headings.
- **UI polish batch 3** (2026-07-15, completes the Pulley visual list): term-sheet scanner shows the **pasted document with flagged clauses highlighted** beside the findings (overlapping matches merged by severity); scenario modeler gains a **stage matrix** — Today → After SAFEs convert → After the round with per-stage deltas (new `after_safes_pct` on scenario rows); the **incorporation wizard** gets a live SPICe+ summary preview with a pending-items notice; progress **steppers** on funnel prospects and SPV co-investor lifecycles; a **workspace switcher** with avatar initials in the top bar; and an **offer builder** (FR-R-2 adjunct) — 1–3 compensation packages with Pulley-style package cards, an illustrative equity-value projection at FMV multiples, and one-click offer-letter generation (new `offer_letter_packages` template). 209 backend tests.
- **Visual-language pass** (2026-07-16, cross-competitor inspiration, presentation-only): reusable primitives to move surfaces beyond bare tables/numbers — **EmptyState** (icon + title + hint + action) replacing "No X yet." across Cap Table, ESOP, Documents, Team, Investors, Data Room and Diligence; **ProgressRing** circular gauges for the diligence readiness score and compliance health; **BarChart** rendering the liquidation waterfall as horizontal payout bars instead of a number table; **PageHeader** (icon · title · subtitle · action) on the Team tab; and **metric icons** on `Stat` cards (ESOP overview). No backend/schema change.
- **trica visual batch** (2026-07-16): **ESOP overview dashboard** (FR-D-1) atop the ESOP tab — pool-usage hero stats, option-state tiles (vested/exercised/exercisable/unvested), a pool-composition donut and a top-grants leaderboard, from a read-only `GET /esop/overview` aggregation; and **info tooltips** on stat cards (`Stat` gained an optional `hint`, applied across the Dashboard, Portal and ESOP overview). No schema change. 261 backend tests.
- **trica functional batch** (2026-07-16): **Ind AS 102 ESOP expense report** (new FR-D-7 ✅) — grant-date fair value (Black-Scholes for options, full FMV for RSU/RSA) amortised straight-line over vesting, aggregated by Indian financial year, with recognised/unrecognised totals and a generated report document (`services/sbp.py`, `esop_expense` template; the fifth competitor to flag SBP expensing); **periodic investor report** (new FR-K-8 ✅) — live metrics snapshot (cap table, valuation, runway, compliance) + founder highlights → report document (`services/reporting.py`, reuses the dashboard + runway services); **ESOP adoption pack** (FR-D-1) — one-click board resolution + EGM notice (s.62(1)(b) special resolution) + ESOP policy (`esop.generate_scheme_pack`, `esop_egm_notice`/`esop_policy` templates). No schema change (all document-generation over existing data). 259 backend tests.
- **Ledgy functional batch** (2026-07-16): **exercise windows** (FR-D-4) — opt-in open/upcoming/closed periods (`exercise_windows`) that gate exercise requests once defined; and **company liquidity / buyback-tender windows** (new FR-C-13 ✅) — `liquidity_events` + `tenders`: admin opens a fixed-price window, holders tender from the portal, settlement writes cap-table buybacks; Alembic `f3c5e7a9b1d2`, new routes/models `liquidity`, Esop exercise-windows card, CapTableHub **Liquidity** sub-tab, portal tender UI. 252 backend tests.
- **Ledgy visual batch** (2026-07-16): employee **equity hero** (today's value / max potential value / vested-bar / next-vest & fully-vested dates) reframing the portal ESOP section, and a **per-grant detail view** (new FR-K-3 ✅) — three value stats, a vesting-status segment bar (exercised/settled · vested · unvested, reusing StackedBar) and a vesting timeline with a *today* marker, from `esop.grant_value_summary` + `grant_schedule` and a `GET /portal/grants/{id}/detail` endpoint (own-grant only). Value model: intrinsic (FMV−strike) per unit for options, full FMV for RSUs/RSAs. No schema change. 248 backend tests.
- **Mantle functional batch 2** (2026-07-16): **fund look-through / Schedule of Investments** (new FR-J-11 ✅) — GP-facing SOI (cost / mark / MOIC / %NAV / unrealised gain per holding + totals + generated statement document, new `soi_statement` template) via `GET /funds/{id}/soi`; LP-facing look-through folded into the portal (`look_through` per fund) showing each LP's pro-rata exposure to the underlying holdings at the fund's own marks. No schema change (read-only over existing portfolio marks). Incidental: removed a pre-existing unused `CENTS` import in `services/fund.py` surfaced by ruff. 242 backend tests.
- **Mantle functional batch** (2026-07-15): **RSU / RSA instruments** (FR-D-2) — the ESOP grant model gained a `grant_type` (option | rsu | rsa) sharing the vesting engine: RSUs settle to shares at vest for no strike with full-FMV perquisite, RSAs issue shares upfront with perquisite at allotment and an unvested-at-repurchase-risk figure; Alembic `e1a3c5b7d9f0`; grant-type tabs + type-aware table in the ESOP screen. **External advisor workspace** (FR-A-2) — `AdvisorAccess` grants a law firm / CA / CS scoped cross-tenant access (viewer/member) enforced via a shared `deps._entity_role`, an entity-side Advisors management tab, and a `/advisor` console listing all client entities; Alembic `e2b4d6c8f0a2`. 238 backend tests.
- **Mantle visual batch** (2026-07-15): **100%-stacked ownership bar** above the cap-table holdings (FR-T-9 ✅); **avatar-initials chips** on stakeholder/holder rows; **document card grid** with per-type tag chips (replacing the flat list); **portal value hero** (FR-K-1) — big current marked value over a value-over-time line chart with 3M/6M/1Y/All range toggles, from a new read-only `/portal/value-history` (holdings × FMV at each valuation date); **app-wide Tasks hub** (FR-T-3) — `/entities/{id}/tasks` aggregating pending signatures, open exercise requests, overdue compliance and outstanding consents, ranked, deep-linking to the resolving tab. Reusable `StackedBar` / `Avatar` components; no schema changes. 229 backend tests.
- **Eqvista functional batch** (2026-07-15): **self-serve indicative valuation** (FR-L-3 ✅) — scorecard / VC-method / DCF-lite blended by custom weights, per-share on the fully-diluted count, smartfill from financial snapshots, saved scenarios, and a workpaper document (`ValuationEstimate`, Alembic `d4f6a8c0b2e4`, new `valuation_estimate` template); **FMV-over-time line chart** (FR-L-2) — registered valuations plus saved indicative estimates as two series. Dependency-free SVG `LineChart` component; Valuations tab split into Reports & FMV | Indicative estimate sub-tabs. 225 backend tests.
- **Eqvista visual batch** (2026-07-15, read-only API + presentation): dashboard **donut charts** for class ownership and share usage with an authorized/issued/available capital panel (authorized derived from the incorporation charter) and a **valuation status card** (active / expired / missing, FR-T-3); **quick-actions row** deep-linking via `?tab=`; **narrative equity timeline** (FR-C-10) — every ledger/equity event as a plain-language sentence, newest first, on a new Cap Table sub-tab; **tinted security-class chips** (coloured by class kind) across cap-table and portal holdings tables; **holdings pivot** — the cap table re-slices client-side as Positions | By stakeholder | By class; **portal vesting projection** (FR-D-3) — vesting-progress stat cards, vested/unvested progress bar, estimated full-vest date and upcoming vest events. No schema changes. 215 backend tests.
- **Savvi/PaperOS gap batch** (2026-07-15): **diligence readiness engine** (FR-I-5 ◐) — 11 rules-as-data checks, severity-weighted score, findings with deep links, report-as-document; **public fundraising funnel** (FR-E-8) — shareable opt-in link per round (unauthenticated, rate-limited), prospects land in the CRM with optional automatic data-room access, admin funnel view; **financing doc automation** — SPV subscription agreements generated on commitment + portal PDF download (FR-S-1), PAS-4 offer letters per round commitment (new FR-E-10 ✅); **small fills** — founder IP assignments in the incorporation pack (FR-B-1), charter-amendment one-step (FR-G-2), offboarding with automatic option lapse (FR-R-4 ✅). Alembic `b9a1d3e5f7c9`; 204 backend tests.

**v1.2 (2026-07-08)** — stage-based guided workspace + grouped navigation (new **FR-T-7**, **FR-T-8**):
- Companies get a lifecycle stage (Inception / Pre-seed / Seed / Series rounds / Pre-IPO): stage-filtered navigation and feature gates, a per-stage auto-checked "what to do now" checklist with deep links, data-driven stage suggestion, free skipping between stages, and an "All features" escape hatch. Stage registry is rules-as-data (`app/stages.py`); Alembic revision `c3e5a7b9d1f2`; 151 backend tests.
- Workspace navigation regrouped into a two-level menu (Home / Ownership / Fundraise / Governance / Operations / Partners; Fund group for funds) replacing the flat ~20-tab row.
- **NFR-13**: all recorded times unified to IST (UTC+05:30) via a single platform clock (`app/clock.py`); JWT expiry remains UTC per RFC 7519.
- **FR-E-9**: family & friends investing — investor kind on SAFEs/commitments, automatic portal visibility for F&F by email, Sec 42 200-offeree/FY guardrail (Alembic `d4f6b8c0e2a4`).
- Journey hardening: outstanding SAFEs/notes now **auto-convert on round close** (FR-E-6); completing a stage checklist offers a one-click "Start next stage"; an end-to-end founder-journey test walks inception → pre-seed → seed → suggested Series. 157 backend tests.

**v1.1 (2026-07-03)** — depth batch:
- **FR-C-1 → ✅**: fully-diluted cap-table view (options outstanding + unallocated pool + SAFEs/notes as-if-converted at assumed price / current FMV), with UI toggle.
- **FR-C-3 → ✅**: anti-dilution terms per security class (broad-based weighted average / full ratchet) + down-round calculator (API + UI).
- **FR-J-5**: distributions upgraded to a cumulative European waterfall — ROC → preferred return (hurdle) → 100% GP catch-up → carry split — with per-tier breakdown stored per distribution and shown in the Fund tab; distributions accept an as-of date.
- Alembic revision `b1c9d2e4f6a8` (distribution breakdown columns, anti-dilution columns); 145 backend tests.

**v1.0 (2026-06-28)** — reconciled with implementation:
- Added per-FR implementation status (✅/◐/○/⛔) across all modules.
- **New module U** (Finance: runway/burn) and **new FRs**: FR-C-11 founder reverse-vesting, FR-C-12 CSV export, FR-E-8 investor CRM/pipeline, FR-K-5 employee equity portal, FR-M-10 alerts/reminder engine.
- Promoted-in-practice P2 items now implemented: audit log (A-5), DPIIT (B-6), multi-state registrations (B-8), valuation-linked ESOP (D-5), closing mechanics + FC-GPR (E-6), director register + DIR-12 (G-4), D&O indemnification (G-6), health score (H-6), diligence Q&A (I-4), SPV (J-9), conditional workflow branching (N-4), tax vault (T-4), cashless exercise (D-4 partial).
- Module renames to reflect scope: B (+ Startup India), E (+ Investor CRM), G (+ Directors), H (+ GST/TDS), K (Investor/LP/Employee), M (+ Alerts).
- Data model: added v1.0 entities (§6.2–6.9), rewrote the relationship spine, added **§6.11 as-built deviations** (Stakeholder-vs-Party, computed snapshots, document-backed certificates/term sheets, same-tenant SPV linkage).
- Added **NFR-12** (Alembic migrations required — `create_all` schema-drift observed in dev).
- §8 anchors: added event-based ROC forms, GST/TDS, registers, with status column.
- §9 rewritten as as-built status + Phase-3 frontier; §10 updated with decisions taken and two new questions.

**v0.1 (2026-06-25)** — original draft from PaperOS capability analysis.

---

*Sources for PaperOS capability grounding:* [PaperOS Knowledge Center — Cap Table & Corporate Record Setup](https://learn.paperos.com/cap-table-setup-request), [paperos.com](https://paperos.com/plans). *Companion documents:* `HLD.md` (architecture), `DEPLOYMENT.md` (deferred infra plan).

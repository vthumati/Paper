import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

/**
 * "Getting started" — a self-contained, business-facing guide.
 *
 * The guide is split by AUDIENCE (organisation type): a founder running a
 * startup, a fund manager, an SPV/syndicate lead, and an investor/LP. The user
 * picks their type on the landing page and only ever sees the topics relevant
 * to that type. Content is static prose styled with the shared token system —
 * no data fetching.
 *
 * Routes:
 *   /guide                       landing — pick your organisation type
 *   /guide/:audience             topic grid for that type
 *   /guide/:audience/:topicId    a single topic, with prev/next
 */

// ── small presentational helpers ────────────────────────────────────────────

/** A numbered how-to step. */
function Step({ n, title, children }: { n: number; title: string; children?: ReactNode }) {
  return (
    <li style={{ display: "flex", gap: 12, listStyle: "none" }}>
      <span
        style={{
          display: "grid",
          placeItems: "center",
          width: 24,
          height: 24,
          flex: "0 0 auto",
          borderRadius: "50%",
          background: "var(--navy)",
          color: "#fff",
          fontSize: 12,
          fontWeight: 700,
        }}
      >
        {n}
      </span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontWeight: 600, color: "var(--heading)", fontSize: 14 }}>{title}</div>
        {children && (
          <div className="muted" style={{ marginTop: 2, lineHeight: 1.5 }}>
            {children}
          </div>
        )}
      </div>
    </li>
  );
}

/** Highlighted aside — a tip or thing to watch for. */
function Callout({ children }: { children: ReactNode }) {
  return (
    <div
      style={{
        display: "flex",
        gap: 10,
        borderRadius: "var(--radius-sm)",
        background: "var(--light)",
        border: "1px solid var(--border)",
        padding: 12,
      }}
    >
      <span style={{ flex: "0 0 auto" }}>💡</span>
      <p style={{ margin: 0, fontSize: 13, color: "var(--heading)", lineHeight: 1.5 }}>{children}</p>
    </div>
  );
}

/** A subheading inside a topic body. */
function Sub({ icon, title, children }: { icon: string; title: string; children: ReactNode }) {
  return (
    <div>
      <h3 style={{ display: "flex", alignItems: "center", gap: 8, margin: "0 0 6px" }}>
        <span>{icon}</span>
        {title}
      </h3>
      <div className="muted" style={{ lineHeight: 1.5, display: "flex", flexDirection: "column", gap: 8 }}>
        {children}
      </div>
    </div>
  );
}

// ── audiences & topics ──────────────────────────────────────────────────────

type Audience = "startup" | "fund" | "spv" | "investor";

interface AudienceDef {
  key: Audience;
  label: string;
  icon: string;
  tagline: string;
  /** Which entity type(s) this maps to when you create a workspace. */
  entityTypes: string;
}

const AUDIENCES: AudienceDef[] = [
  {
    key: "startup",
    label: "Startup / Company",
    icon: "🚀",
    tagline: "Incorporate, own equity, raise, and stay compliant.",
    entityTypes: "Pvt Ltd · LLP · OPC",
  },
  {
    key: "fund",
    label: "Fund (AIF)",
    icon: "🏦",
    tagline: "Run a SEBI AIF end to end — LPs, deals, NAV, distributions.",
    entityTypes: "Fund",
  },
  {
    key: "spv",
    label: "SPV / Syndicate",
    icon: "🤝",
    tagline: "Pool investors into a single vehicle for one deal.",
    entityTypes: "SPV",
  },
  {
    key: "investor",
    label: "Investor / LP",
    icon: "💼",
    tagline: "Commit to deals and track your holdings in the portal.",
    entityTypes: "Portal access",
  },
];

interface Topic {
  id: string;
  audience: Audience;
  group: string;
  title: string;
  blurb: string;
  minutes: number;
  icon: string;
  body: ReactNode;
}

const TOPICS: Topic[] = [
  // ── STARTUP ────────────────────────────────────────────────────────────────
  {
    id: "workspace",
    audience: "startup",
    group: "Set up",
    title: "Set up your workspace & incorporate",
    blurb: "Create your organisation, then incorporate or add an existing company.",
    minutes: 3,
    icon: "🏢",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          Everything in Paper lives under an <strong>organisation</strong> (your workspace). Inside
          it you create one or more <strong>legal entities</strong> — a Pvt Ltd, LLP or OPC — and
          each entity gets its own cap table, documents and compliance calendar.
        </p>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Create an organisation">
            From the home screen, add an organisation to hold your entities.
          </Step>
          <Step n={2} title="Incorporate a new company">
            Use the <strong>Incorporation wizard</strong> to spin up a fresh Pvt Ltd — it captures
            directors, subscribers and authorised capital and drafts the incorporation set.
          </Step>
          <Step n={3} title="…or add an existing entity">
            Already incorporated? Add the entity with its name, type and CIN to bring it under
            management.
          </Step>
          <Step n={4} title="Set your stage">
            Open the entity and pick a <strong>stage</strong> (idea → pre-seed → seed …). The stage
            controls which features surface first, so you are never shown more than you need.
          </Step>
        </ol>
        <Callout>
          Stages are only a guide — flip to <strong>All features</strong> anytime to see everything,
          and nothing is ever hidden permanently.
        </Callout>
      </>
    ),
  },
  {
    id: "captable",
    audience: "startup",
    group: "Own",
    title: "Build your cap table",
    blurb: "Security classes, stakeholders, issuances and a fully-diluted view.",
    minutes: 4,
    icon: "📊",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          The cap table is the source of truth for who owns what. Build it once and every round,
          grant and report reads from it.
        </p>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Add security classes">
            Define your equity and preference classes (e.g. Equity, CCPS) under Cap Table.
          </Step>
          <Step n={2} title="Add stakeholders & issue shares">
            Add founders and early holders, then record issuances against a class. Ownership
            percentages update instantly.
          </Step>
          <Step n={3} title="Turn on founder vesting">
            Put founder shares on a vesting schedule so unvested equity returns to the company on an
            early exit.
          </Step>
          <Step n={4} title="Read the fully-diluted view">
            See ownership on a fully-diluted basis — including the option pool and convertibles — and
            a 100%-stacked ownership bar.
          </Step>
        </ol>
        <Callout>
          Have a spreadsheet already? Use <strong>Import cap table</strong> (CSV) to load holders and
          holdings in one shot.
        </Callout>
      </>
    ),
  },
  {
    id: "esop",
    audience: "startup",
    group: "Own",
    title: "Grant ESOPs",
    blurb: "Create a pool, issue grants with vesting, and handle exercises.",
    minutes: 3,
    icon: "🎯",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          Attract talent with equity. Paper manages the pool, vesting and the Ind AS 102 expense so
          your ESOP is board- and audit-ready.
        </p>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Create an option pool">
            Reserve a pool on the cap table — it shows up in the fully-diluted view.
          </Step>
          <Step n={2} title="Issue grants">
            Grant options to employees with a vesting schedule and cliff. Onboarding a team member
            can link them to a grant automatically.
          </Step>
          <Step n={3} title="Adopt the scheme">
            Generate the ESOP adoption pack (scheme + board/shareholder resolutions) from Documents.
          </Step>
          <Step n={4} title="Process exercises">
            Employees raise exercise requests; approve them to convert vested options into shares.
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: "raise",
    audience: "startup",
    group: "Raise",
    title: "Raise a round",
    blurb: "Open a round, collect commitments, generate documents, and close.",
    minutes: 5,
    icon: "🚀",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          <strong>Rounds &amp; SAFEs</strong> takes you from opening a priced round through to
          allotment — with the FEMA and Companies Act paperwork handled along the way.
        </p>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Open a round">
            Set the name, pre-money, target and price per share, and pick the security class.
          </Step>
          <Step n={2} title="Share a data room & run the funnel">
            Publish a data room, create a share link, and track prospects through the investor funnel
            (contacted → committed).
          </Step>
          <Step n={3} title="Add commitments">
            Record each investor's cheque, kind and whether they are foreign, then generate a{" "}
            <strong>PAS-4</strong> private-placement offer letter per investor.
          </Step>
          <Step n={4} title="Generate the term sheet">
            Produce the term sheet, and use the scanner to flag off-market terms before you sign.
          </Step>
          <Step n={5} title="Close the round">
            Closing issues the allotments, converts any SAFEs/notes, and — for foreign money — adds
            the FC-GPR FEMA filing to Compliance.
          </Step>
        </ol>
        <Callout>
          Raising on a <strong>SAFE</strong> or convertible note instead? Use the SAFE execution flow
          (terms → board approval → agreement → e-sign); it converts automatically at your next
          priced round.
        </Callout>
      </>
    ),
  },
  {
    id: "diligence",
    audience: "startup",
    group: "Raise",
    title: "Get diligence-ready",
    blurb: "See what investors will ask for — before they ask.",
    minutes: 2,
    icon: "🔍",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          The <strong>Diligence</strong> readiness engine checks your workspace against what a
          typical investor requests and scores your readiness.
        </p>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Open Diligence">
            Review the checklist of documents and data points, grouped by area.
          </Step>
          <Step n={2} title="Close the gaps">
            Each open item links straight to the tab that fixes it (cap table, governance, compliance
            …).
          </Step>
          <Step n={3} title="Share the data room">
            When your score is healthy, grant data-room access to your funnel prospects.
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: "governance",
    audience: "startup",
    group: "Govern",
    title: "Governance & compliance",
    blurb: "Board resolutions, statutory registers, filings and Startup India.",
    minutes: 4,
    icon: "⚖️",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          Stay on the right side of the Companies Act without a company secretary chasing you.
        </p>
        <Sub icon="📝" title="Board & resolutions">
          <p>
            Pass board and shareholder resolutions, amend the charter, and capture investor consents
            where a resolution needs them.
          </p>
        </Sub>
        <Sub icon="📚" title="Registers">
          <p>Statutory registers (members, directors, charges) are maintained from your cap-table and governance data.</p>
        </Sub>
        <Sub icon="📅" title="Compliance calendar">
          <p>
            Recurring ROC/FEMA/tax obligations appear on a calendar with due dates, so nothing is
            missed.
          </p>
        </Sub>
        <Sub icon="🇮🇳" title="Startup India">
          <p>Track DPIIT recognition and the benefits that come with it from the Startup India tab.</p>
        </Sub>
      </>
    ),
  },
  {
    id: "operate",
    audience: "startup",
    group: "Run",
    title: "Run day-to-day",
    blurb: "Team, contracts, finance, valuations, documents and workflows.",
    minutes: 3,
    icon: "🛠️",
    body: (
      <>
        <Sub icon="👥" title="Team & offers">
          <p>
            Build offer letters, onboard employees and contractors (which can generate HR docs and
            link to the cap table), and offboard cleanly — unvested options lapse back to the pool.
          </p>
        </Sub>
        <Sub icon="📄" title="Contracts & documents">
          <p>Draft and store contracts; every generated document lands in Documents and Files.</p>
        </Sub>
        <Sub icon="💰" title="Finance & valuations">
          <p>
            Track finances and record valuations (scorecard, VC and DCF methods with weighting) plus
            an FMV-over-time chart for 409A-style needs.
          </p>
        </Sub>
        <Sub icon="⚙️" title="Workflows & marketplace">
          <p>
            Run guided workflows, and tap the <strong>Marketplace</strong>, <strong>Advisors</strong>{" "}
            and <strong>Managed Admin</strong> when you want a professional to take something off your
            plate.
          </p>
        </Sub>
      </>
    ),
  },

  // ── FUND ─────────────────────────────────────────────────────────────────
  {
    id: "fund-setup",
    audience: "fund",
    group: "Set up",
    title: "Set up your fund (AIF)",
    blurb: "Create the fund entity and open the fund admin workspace.",
    minutes: 3,
    icon: "🏦",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          A fund in Paper is an entity of type <strong>Fund</strong>. Once created, the{" "}
          <strong>Fund (AIF)</strong> workspace unlocks LP management, deals, NAV and distributions.
        </p>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Add a Fund entity">
            Under an organisation, add an entity of type <strong>Fund</strong>.
          </Step>
          <Step n={2} title="Set fund terms">
            Configure the economics you will hold LPs to — management fee, hurdle and carry.
          </Step>
          <Step n={3} title="Open the Fund tab">
            The Fund workspace is where capital accounts, the deal pipeline and NAV all live.
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: "fund-lps",
    audience: "fund",
    group: "Capital",
    title: "Onboard LPs & capital",
    blurb: "Bring in limited partners and track their capital accounts.",
    minutes: 4,
    icon: "🤝",
    body: (
      <>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Add limited partners">
            Record each LP and their commitment to the fund.
          </Step>
          <Step n={2} title="Track capital accounts">
            Contributions, drawdowns and fees flow into a per-LP <strong>capital account</strong>.
          </Step>
          <Step n={3} title="Unitise (optional)">
            Run the fund on a units / NAV-per-unit basis if you prefer a unitised structure.
          </Step>
        </ol>
        <Callout>
          LPs can watch their own position from the <strong>Investor / LP portal</strong> — point
          them to that guide.
        </Callout>
      </>
    ),
  },
  {
    id: "fund-deals",
    audience: "fund",
    group: "Invest",
    title: "Make & track investments",
    blurb: "Deal pipeline, portfolio marks and look-through.",
    minutes: 3,
    icon: "📈",
    body: (
      <>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Run the deal pipeline">
            Move prospective deals through stages until you invest.
          </Step>
          <Step n={2} title="Mark the portfolio">
            Record portfolio marks over time to drive performance and NAV.
          </Step>
          <Step n={3} title="See look-through">
            The Schedule of Investments gives you (and LPs) look-through into the underlying holdings.
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: "fund-economics",
    audience: "fund",
    group: "Economics",
    title: "NAV, fees & distributions",
    blurb: "Management fee, the waterfall, and performance metrics.",
    minutes: 4,
    icon: "💧",
    body: (
      <>
        <Sub icon="🧾" title="Management fee">
          <p>Accrue the management fee and charge it into LP capital accounts.</p>
        </Sub>
        <Sub icon="💧" title="Distribution waterfall">
          <p>
            Model distributions with a <strong>hurdle rate and GP catch-up</strong>, so carry is
            computed correctly on every exit.
          </p>
        </Sub>
        <Sub icon="📊" title="Performance">
          <p>Track <strong>XIRR, DPI and TVPI</strong> at the fund and LP level.</p>
        </Sub>
      </>
    ),
  },
  {
    id: "fund-reporting",
    audience: "fund",
    group: "Report",
    title: "LP reporting & SEBI compliance",
    blurb: "Capital-account statements, Form 64C/64D and the AIF calendar.",
    minutes: 3,
    icon: "📬",
    body: (
      <>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Issue capital-account statements">
            Generate per-LP statements as documents they can access in the portal.
          </Step>
          <Step n={2} title="Produce tax statements">
            Generate <strong>Form 64C / 64D</strong> AIF tax statements at year end.
          </Step>
          <Step n={3} title="Work the AIF calendar">
            The SEBI AIF compliance calendar tracks recurring filings and their due dates.
          </Step>
        </ol>
      </>
    ),
  },

  // ── SPV ──────────────────────────────────────────────────────────────────
  {
    id: "spv-setup",
    audience: "spv",
    group: "Set up",
    title: "Create the SPV",
    blurb: "Spin up a single-deal vehicle and set its terms.",
    minutes: 3,
    icon: "🤝",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          An <strong>SPV</strong> pools several investors into one vehicle for a single deal. Create
          an entity of type <strong>SPV</strong> to open the SPV workspace.
        </p>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Add an SPV entity">
            Under an organisation, add an entity of type <strong>SPV</strong>.
          </Step>
          <Step n={2} title="Set SPV terms">
            Configure <strong>carry %</strong>, the minimum ticket, and a provisioning fund profile
            for expenses.
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: "spv-raise",
    audience: "spv",
    group: "Raise",
    title: "Run the syndicate raise",
    blurb: "Invite investors, collect commitments, and fund the deal.",
    minutes: 4,
    icon: "📨",
    body: (
      <>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Invite investors">
            Send invitations to your syndicate — each gets a portal link to review the deal.
          </Step>
          <Step n={2} title="Collect commitments">
            Investors commit in their portal; you watch commitments roll in against the target.
          </Step>
          <Step n={3} title="Fund & track positions">
            Mark commitments funded; co-investors see their SPV position in their own portal.
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: "spv-manage",
    audience: "spv",
    group: "Manage",
    title: "Close & manage the deal",
    blurb: "Record the position and distribute proceeds later.",
    minutes: 2,
    icon: "✅",
    body: (
      <>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Record the investment">
            Capture the SPV's holding in the target company.
          </Step>
          <Step n={2} title="Distribute on exit">
            When the deal returns cash, distribute to co-investors net of carry.
          </Step>
        </ol>
      </>
    ),
  },

  // ── INVESTOR / LP ──────────────────────────────────────────────────────────
  {
    id: "inv-access",
    audience: "investor",
    group: "Get in",
    title: "Access your portal",
    blurb: "Log in and find the portfolio view built for investors.",
    minutes: 2,
    icon: "🔑",
    body: (
      <>
        <p className="muted" style={{ lineHeight: 1.5 }}>
          Whether you are an angel, an LP in a fund, or a co-investor in an SPV, the{" "}
          <strong>Portal</strong> is your home — a single portfolio view across everything you are in.
        </p>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Log in">
            Sign in with the account tied to your investments, then open <strong>Portal</strong> from
            the top bar.
          </Step>
          <Step n={2} title="Read your portfolio hero">
            The portal opens on your total portfolio value with time-range toggles to see how it has
            moved.
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: "inv-commit",
    audience: "investor",
    group: "Invest",
    title: "Commit to a deal",
    blurb: "Follow an invite link and commit in a few steps.",
    minutes: 2,
    icon: "✍️",
    body: (
      <>
        <ol style={{ display: "flex", flexDirection: "column", gap: 12, paddingLeft: 0 }}>
          <Step n={1} title="Open the invite link">
            A startup or syndicate lead shares a link — it opens the deal and any shared data room.
          </Step>
          <Step n={2} title="Review the data room">
            Read the materials; your views are visible to the raiser so they know you are engaged.
          </Step>
          <Step n={3} title="Commit">
            Enter your cheque size to register a commitment. The raiser confirms and, for SPVs/funds,
            it flows into your capital account.
          </Step>
        </ol>
      </>
    ),
  },
  {
    id: "inv-track",
    audience: "investor",
    group: "Track",
    title: "Track holdings & documents",
    blurb: "Positions, capital accounts, vesting, statements and consents.",
    minutes: 3,
    icon: "📂",
    body: (
      <>
        <Sub icon="📊" title="Positions">
          <p>See each holding — direct shares, LP interests and SPV positions — in one place.</p>
        </Sub>
        <Sub icon="🧾" title="Capital accounts & statements">
          <p>
            As an LP, review your capital account and download capital-account and tax statements as
            the fund issues them.
          </p>
        </Sub>
        <Sub icon="🎯" title="Vesting">
          <p>If you also hold options as an employee, your vesting schedule shows here too.</p>
        </Sub>
        <Sub icon="🗳️" title="Consents">
          <p>When a company or fund needs your sign-off on a resolution, you record your consent from the portal.</p>
        </Sub>
      </>
    ),
  },
];

// Topics for an audience, in authored order (drives step numbers & prev/next).
const topicsFor = (a: Audience) => TOPICS.filter((t) => t.audience === a);

// Group labels in first-seen order, for the landing sections.
function groupsFor(a: Audience): string[] {
  const seen: string[] = [];
  for (const t of topicsFor(a)) if (!seen.includes(t.group)) seen.push(t.group);
  return seen;
}

function isAudience(v: string | undefined): v is Audience {
  return !!v && AUDIENCES.some((a) => a.key === v);
}

// ── pages ─────────────────────────────────────────────────────────────────────

export default function GettingStarted() {
  const { audience, topicId } = useParams<{ audience: string; topicId: string }>();
  if (isAudience(audience)) {
    if (topicId) return <TopicPage audience={audience} topicId={topicId} />;
    return <TopicGrid audience={audience} />;
  }
  return <AudiencePicker />;
}

/** Landing — choose your organisation type. */
function AudiencePicker() {
  return (
    <div>
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 8 }}>
        <span style={{ fontSize: 30 }}>💡</span>
        <div>
          <h1 style={{ margin: 0 }}>Getting started</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>
            Pick what you are — we'll show only the guides that apply to you.
          </p>
        </div>
      </div>

      <div className="doc-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", marginTop: 16 }}>
        {AUDIENCES.map((a) => (
          <Link key={a.key} to={`/guide/${a.key}`} className="card guide-card" style={{ display: "block" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span
                style={{
                  display: "grid",
                  placeItems: "center",
                  width: 44,
                  height: 44,
                  flex: "0 0 auto",
                  borderRadius: "var(--radius-sm)",
                  background: "var(--light)",
                  fontSize: 24,
                }}
              >
                {a.icon}
              </span>
              <div style={{ minWidth: 0 }}>
                <div style={{ fontWeight: 700, color: "var(--heading)" }}>{a.label}</div>
                <div className="muted" style={{ fontSize: 12 }}>
                  {a.entityTypes}
                </div>
              </div>
            </div>
            <p className="muted" style={{ margin: "10px 0 0", lineHeight: 1.5 }}>
              {a.tagline}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}

/** Topic grid for one audience, grouped and step-numbered. */
function TopicGrid({ audience }: { audience: Audience }) {
  const def = AUDIENCES.find((a) => a.key === audience)!;
  const topics = topicsFor(audience);

  return (
    <div>
      <p className="muted">
        <Link to="/guide">← All guides</Link>
      </p>

      {/* audience switcher */}
      <div className="tabs">
        {AUDIENCES.map((a) => (
          <Link key={a.key} to={`/guide/${a.key}`} className={a.key === audience ? "active" : ""}
            style={{
              padding: "6px 4px",
              borderBottom: a.key === audience ? "2px solid var(--heading)" : "2px solid transparent",
              marginBottom: -2,
              color: a.key === audience ? "var(--heading)" : "var(--blue)",
              fontWeight: a.key === audience ? 700 : 400,
              fontSize: 14,
            }}
          >
            {a.icon} {a.label}
          </Link>
        ))}
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 10, margin: "4px 0 16px" }}>
        <span style={{ fontSize: 26 }}>{def.icon}</span>
        <div>
          <h1 style={{ margin: 0 }}>{def.label}</h1>
          <p className="muted" style={{ margin: "2px 0 0" }}>{def.tagline}</p>
        </div>
      </div>

      {groupsFor(audience).map((g) => (
        <section key={g} style={{ marginBottom: 18 }}>
          <h2 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.06em", color: "var(--muted)", marginBottom: 8 }}>
            {g}
          </h2>
          <div className="doc-grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))" }}>
            {topics
              .filter((t) => t.group === g)
              .map((t) => {
                const step = topics.findIndex((x) => x.id === t.id) + 1;
                return (
                  <Link key={t.id} to={`/guide/${audience}/${t.id}`} className="card guide-card" style={{ display: "block" }}>
                    <div style={{ display: "flex", gap: 10, alignItems: "flex-start" }}>
                      <span
                        style={{
                          display: "grid",
                          placeItems: "center",
                          width: 40,
                          height: 40,
                          flex: "0 0 auto",
                          borderRadius: "var(--radius-sm)",
                          background: "var(--light)",
                          fontSize: 20,
                        }}
                      >
                        {t.icon}
                      </span>
                      <div style={{ minWidth: 0, flex: 1 }}>
                        <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)" }}>
                          STEP {step} · {t.minutes} min read
                        </div>
                        <div style={{ fontWeight: 700, color: "var(--heading)", marginTop: 2 }}>{t.title}</div>
                        <p className="muted" style={{ margin: "4px 0 0", lineHeight: 1.5 }}>{t.blurb}</p>
                      </div>
                    </div>
                  </Link>
                );
              })}
          </div>
        </section>
      ))}
    </div>
  );
}

/** A single topic, with prev/next within the audience. */
function TopicPage({ audience, topicId }: { audience: Audience; topicId: string }) {
  const nav = useNavigate();
  const topics = topicsFor(audience);
  const idx = topics.findIndex((t) => t.id === topicId);
  const topic = topics[idx];
  const def = AUDIENCES.find((a) => a.key === audience)!;

  if (!topic) {
    return (
      <div className="card" style={{ textAlign: "center", padding: 32 }}>
        <p className="muted">That guide doesn't exist.</p>
        <Link to={`/guide/${audience}`}>
          <button className="secondary" style={{ marginTop: 8 }}>Back to {def.label}</button>
        </Link>
      </div>
    );
  }

  const prev = idx > 0 ? topics[idx - 1] : null;
  const next = idx < topics.length - 1 ? topics[idx + 1] : null;

  return (
    <div style={{ maxWidth: 760 }}>
      <p className="muted">
        <Link to={`/guide/${audience}`}>← {def.label}</Link>
      </p>

      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <span
          style={{
            display: "grid",
            placeItems: "center",
            width: 46,
            height: 46,
            flex: "0 0 auto",
            borderRadius: "var(--radius-sm)",
            background: "var(--light)",
            fontSize: 24,
          }}
        >
          {topic.icon}
        </span>
        <div>
          <div style={{ fontSize: 11, fontWeight: 600, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.04em" }}>
            Step {idx + 1} · {topic.minutes} min read
          </div>
          <h1 style={{ margin: 0, lineHeight: 1.2 }}>{topic.title}</h1>
        </div>
      </div>

      <div className="card" style={{ display: "flex", flexDirection: "column", gap: 16 }}>{topic.body}</div>

      <div style={{ display: "flex", justifyContent: "space-between", gap: 12, marginTop: 16 }}>
        {prev ? (
          <button className="secondary" onClick={() => nav(`/guide/${audience}/${prev.id}`)}>
            ← {prev.title}
          </button>
        ) : (
          <span />
        )}
        {next && (
          <button onClick={() => nav(`/guide/${audience}/${next.id}`)}>{next.title} →</button>
        )}
      </div>
    </div>
  );
}

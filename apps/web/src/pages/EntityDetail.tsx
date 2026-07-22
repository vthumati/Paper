import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, type Entity, type StageGuide } from "../api";
import CapTableHub from "../features/CapTableHub";
import FundraisingHub from "../features/FundraisingHub";
import Documents from "../features/Documents";
import Compliance from "../features/Compliance";
import Fund from "../features/Fund";
import Esop from "../features/Esop";
import ExerciseRequests from "../features/ExerciseRequests";
import Valuations from "../features/Valuations";
import Advisors from "../features/Advisors";
import Services from "../features/Services";
import Admin from "../features/Admin";
import Spv from "../features/Spv";
import Governance from "../features/Governance";
import Dashboard from "../features/Dashboard";
import FundDashboard from "../features/FundDashboard";
import TasksHub from "../features/TasksHub";
import Team from "../features/Team";
import Contracts from "../features/Contracts";
import Investors from "../features/Investors";
import StartupIndia from "../features/StartupIndia";
import Finance from "../features/Finance";
import Registers from "../features/Registers";
import Diligence from "../features/Diligence";
import OfferBuilder from "../features/OfferBuilder";

type Tab =
  | "dashboard"
  | "tasks"
  | "team"
  | "contracts"
  | "investors"
  | "captable"
  | "fundraising"
  | "governance"
  | "documents"
  | "diligence"
  | "compliance"
  | "esop"
  | "valuations"
  | "services"
  | "advisors"
  | "admin"
  | "spv"
  | "startup"
  | "finance"
  | "registers"
  // fund workspace tabs (promoted from the old single "Fund" tab's sub-tabs)
  | "capital"
  | "fundraise"
  | "portfolio"
  | "monitoring"
  | "deals"
  | "plan"
  | "reports";

// Two-level navigation: tabs live in groups; the group row is always visible
// and the sub-tab row shows the active group's tabs.
// scope: which entity types see the tab at all (stage then filters companies)
// group keys and tab keys are separate namespaces (a def carries both a `key`
// (Tab) and a `group` (Group)); fund work is split into three groups.
type Group =
  | "home"
  | "fundmgmt"
  | "portfolio"
  | "monitoring"
  | "spv"
  | "ownership"
  | "raise"
  | "govern"
  | "operate"
  | "partners";

const GROUPS: { key: Group; label: string }[] = [
  { key: "home", label: "Home" },
  { key: "fundmgmt", label: "Fund management" },
  { key: "portfolio", label: "Portfolio" },
  { key: "monitoring", label: "Monitoring" },
  { key: "spv", label: "SPV" },
  { key: "ownership", label: "Ownership" },
  { key: "raise", label: "Fundraise" },
  { key: "govern", label: "Governance" },
  { key: "operate", label: "Operations" },
  { key: "partners", label: "Partners" },
];

const TAB_DEFS: {
  key: Tab;
  label: string;
  group: Group;
  scope: "all" | "company" | "fundlike" | "fundonly" | "spvonly";
}[] = [
  { key: "dashboard", label: "Dashboard", group: "home", scope: "all" },
  { key: "tasks", label: "Tasks", group: "home", scope: "all" },
  // the fund workspace — promoted to primary tabs, grouped by what they do
  // Fund management: the fund vehicle + LP relations (LP updates is added
  // dynamically for funds, see `defs` below)
  { key: "capital", label: "Capital & LPs", group: "fundmgmt", scope: "fundonly" },
  { key: "fundraise", label: "LP fundraise", group: "fundmgmt", scope: "fundonly" },
  { key: "plan", label: "Plan & forecast", group: "fundmgmt", scope: "fundonly" },
  { key: "reports", label: "Financials", group: "fundmgmt", scope: "fundonly" },
  // Portfolio: sourcing and holdings
  { key: "deals", label: "Deal pipeline", group: "portfolio", scope: "fundonly" },
  { key: "portfolio", label: "Holdings", group: "portfolio", scope: "fundonly" },
  // Monitoring: portfolio-company performance
  { key: "monitoring", label: "Monitoring", group: "monitoring", scope: "fundonly" },
  { key: "spv", label: "SPV", group: "spv", scope: "spvonly" },
  { key: "captable", label: "Cap Table", group: "ownership", scope: "company" },
  { key: "esop", label: "ESOP", group: "ownership", scope: "company" },
  { key: "valuations", label: "Valuations", group: "ownership", scope: "company" },
  { key: "fundraising", label: "Rounds & SAFEs", group: "raise", scope: "company" },
  { key: "diligence", label: "Diligence", group: "raise", scope: "company" },
  { key: "investors", label: "Investors", group: "raise", scope: "all" },
  { key: "governance", label: "Board & Resolutions", group: "govern", scope: "all" },
  { key: "compliance", label: "Compliance", group: "govern", scope: "all" },
  { key: "registers", label: "Registers", group: "govern", scope: "all" },
  { key: "startup", label: "Startup India", group: "govern", scope: "company" },
  { key: "team", label: "Team", group: "operate", scope: "company" },
  { key: "contracts", label: "Contracts", group: "operate", scope: "company" },
  { key: "finance", label: "Finance", group: "operate", scope: "company" },
  { key: "documents", label: "Documents", group: "operate", scope: "all" },
  { key: "services", label: "Marketplace", group: "partners", scope: "all" },
  { key: "advisors", label: "Advisors", group: "partners", scope: "all" },
  { key: "admin", label: "Managed Admin", group: "partners", scope: "all" },
];

export default function EntityDetail() {
  const { entityId = "" } = useParams();
  const nav = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [entity, setEntity] = useState<Entity | null>(null);
  const [guide, setGuide] = useState<StageGuide | null>(null);
  const [showAll, setShowAll] = useState(false);
  const [tab, setTab] = useState<Tab>("dashboard");

  // ?tab= deep links (command palette, shared URLs); cleared once applied.
  // Legacy ?tab=fund[&sub=X] now maps to the promoted fund tab directly.
  useEffect(() => {
    let wanted = searchParams.get("tab");
    if (wanted === "fund") wanted = searchParams.get("sub") || "capital";
    if (wanted && TAB_DEFS.some((t) => t.key === wanted)) {
      setTab(wanted as Tab);
      setSearchParams({}, { replace: true });
    }
  }, [searchParams]);
  const [capRefresh, setCapRefresh] = useState(0);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .getEntity(entityId)
      .then((e) => {
        setEntity(e);
        if (e.type !== "fund" && e.type !== "spv") {
          api.stageGuide(entityId).then(setGuide).catch(() => {});
        }
      })
      .catch((e) => setError(e.message));
  }, [entityId]);

  // keep the checklist fresh when the user comes back to the dashboard
  useEffect(() => {
    if (tab === "dashboard" && entity && entity.type !== "fund" && entity.type !== "spv") {
      api.stageGuide(entityId).then(setGuide).catch(() => {});
    }
  }, [tab, capRefresh]);

  // if the active tab is no longer visible (stage change / show-all off), go home
  useEffect(() => {
    if (guide && !showAll && tab !== "dashboard" && !guide.tabs.includes(tab)) {
      setTab("dashboard");
    }
  }, [guide, showAll]);

  if (error) return <p className="error">{error}</p>;
  if (!entity) return <p>Loading…</p>;

  const isCompany = entity.type !== "fund" && entity.type !== "spv";
  // for a fund, "Investors" is really the LP-update channel — relabel it and
  // move it under the Fund group so it sits with the rest of fund admin
  const defs =
    entity.type === "fund"
      ? TAB_DEFS.map((t) =>
          t.key === "investors"
            ? { ...t, label: "LP updates", group: "fundmgmt" as Group }
            : t
        )
      : TAB_DEFS;
  const scopeOk = (scope: string) =>
    scope === "all" ||
    (scope === "company" && isCompany) ||
    (scope === "fundlike" && !isCompany) ||
    (scope === "fundonly" && entity.type === "fund") ||
    (scope === "spvonly" && entity.type === "spv");
  const stageOk = (key: Tab) =>
    !isCompany || showAll || !guide || guide.tabs.includes(key);
  const visibleTabs = defs.filter((t) => scopeOk(t.scope) && stageOk(t.key));
  const visibleGroups = GROUPS.filter((g) => visibleTabs.some((t) => t.group === g.key));
  const activeGroup = defs.find((t) => t.key === tab)?.group ?? "home";
  const groupTabs = visibleTabs.filter((t) => t.group === activeGroup);
  const feat = (k: string) => !isCompany || showAll || !guide || guide.features[k] !== false;

  const goTab = (t: string) => setTab(t as Tab);
  const changeStage = async (stage: string) => {
    try {
      setGuide(await api.setStage(entityId, stage));
      setTab("dashboard");
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const changePack = async (pack: string) => {
    try {
      setGuide(await api.setPack(entityId, pack));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  const packLabel = (key: string | null) =>
    guide?.packs.find((p) => p.key === key)?.label ?? key;

  const nextTodos = guide ? guide.checklist.filter((c) => !c.done) : [];

  return (
    <div>
      <p className="muted">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            nav(`/tenants/${entity.tenant_id}/entities`);
          }}
        >
          ← Entities
        </a>
      </p>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ display: "flex", alignItems: "center", gap: 10, flexWrap: "wrap" }}>
          {entity.name} <span className="badge">{entity.type}</span>
        </h1>
        {isCompany && guide && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <select
              value={guide.pack}
              onChange={(e) => changePack(e.target.value)}
              style={{ width: "auto" }}
              title="Feature pack — the plan that decides which tabs are available"
            >
              {guide.packs.map((p) => (
                <option key={p.key} value={p.key}>
                  Plan: {p.label}
                </option>
              ))}
            </select>
            <select
              value={guide.stage}
              onChange={(e) => changeStage(e.target.value)}
              style={{ width: "auto" }}
              title="Company stage — drives the 'what to do now' checklist"
            >
              {guide.stages.map((s) => (
                <option key={s.key} value={s.key}>
                  Stage: {s.label}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {isCompany && guide?.suggested_pack && (
        <div className="card" style={{ borderLeft: "4px solid var(--accent)" }}>
          <p style={{ margin: 0 }}>
            Your data suggests the{" "}
            <strong>{packLabel(guide.suggested_pack)}</strong> plan —{" "}
            {guide.packs.find((p) => p.key === guide.suggested_pack)?.blurb}{" "}
            <button onClick={() => changePack(guide.suggested_pack!)}>
              Upgrade to {packLabel(guide.suggested_pack)}
            </button>
          </p>
        </div>
      )}

      {isCompany && guide?.suggested_stage && (
        <div className="card" style={{ borderLeft: "4px solid var(--accent)" }}>
          <p style={{ margin: 0 }}>
            Based on your data, you look ready for{" "}
            <strong>{guide.stages.find((s) => s.key === guide.suggested_stage)?.label}</strong>.{" "}
            <button onClick={() => changeStage(guide.suggested_stage!)}>
              Move to {guide.stages.find((s) => s.key === guide.suggested_stage)?.label}
            </button>
          </p>
        </div>
      )}

      <div className="tabs">
        {visibleGroups.map((g) => (
          <button
            key={g.key}
            className={activeGroup === g.key ? "active" : ""}
            onClick={() => {
              const first = visibleTabs.find((t) => t.group === g.key);
              if (first) setTab(first.key);
            }}
          >
            {g.label}
          </button>
        ))}
        {isCompany && guide && (
          <button
            className="secondary"
            title="Your plan surfaces what's relevant now; nothing is ever removed"
            onClick={() => setShowAll((v) => !v)}
          >
            {showAll ? "Plan view" : "Show everything"}
          </button>
        )}
      </div>
      {groupTabs.length > 1 && (
        <div className="tabs subtabs">
          {groupTabs.map((t) => (
            <button
              key={t.key}
              className={tab === t.key ? "active" : ""}
              onClick={() => setTab(t.key)}
            >
              {t.label}
            </button>
          ))}
        </div>
      )}

      {tab === "dashboard" && entity.type === "fund" && (
        <FundDashboard entityId={entityId} onNavigate={goTab} />
      )}
      {tab === "dashboard" && entity.type !== "fund" && (
        <>
          {isCompany && guide && (
            <div className="card">
              <h3>
                {guide.label} — what to do now{" "}
                <span className={`badge ${guide.progress.done === guide.progress.total ? "complete" : ""}`}>
                  {guide.progress.done}/{guide.progress.total} done
                </span>
              </h3>
              <p className="muted">{guide.headline}</p>
              {nextTodos.length === 0 ? (
                <p>
                  All {guide.label} steps are done.{" "}
                  {(() => {
                    const i = guide.stages.findIndex((s) => s.key === guide.stage);
                    const next = guide.stages[i + 1];
                    return next ? (
                      <button onClick={() => changeStage(next.key)}>
                        Start {next.label} →
                      </button>
                    ) : null;
                  })()}
                  <span className="muted">
                    {" "}
                    Stages are guides — skip ahead or go back anytime from the picker above.
                  </span>
                </p>
              ) : (
                nextTodos.map((c) => (
                  <div key={c.key} className="list-item" onClick={() => goTab(c.tab)}>
                    <strong>○ {c.title}</strong>
                    <span className="muted"> — {c.hint}</span>
                  </div>
                ))
              )}
              {guide.progress.done > 0 && nextTodos.length > 0 && (
                <p className="muted" style={{ marginBottom: 0 }}>
                  ✓ {guide.progress.done} step{guide.progress.done > 1 ? "s" : ""} completed:{" "}
                  {guide.checklist.filter((c) => c.done).map((c) => c.title).join(" · ")}
                </p>
              )}
            </div>
          )}
          <Dashboard entityId={entityId} />
        </>
      )}
      {tab === "tasks" && <TasksHub entityId={entityId} />}
      {tab === "team" && (
        <>
          <OfferBuilder entityId={entityId} />
          <Team entityId={entityId} />
        </>
      )}
      {tab === "startup" && <StartupIndia entityId={entityId} />}
      {tab === "finance" && <Finance entityId={entityId} />}
      {tab === "registers" && <Registers entityId={entityId} />}
      {tab === "contracts" && <Contracts entityId={entityId} />}
      {tab === "investors" && <Investors entityId={entityId} />}
      {tab === "captable" && (
        <CapTableHub
          entityId={entityId}
          refreshKey={capRefresh}
          onChanged={() => setCapRefresh((x) => x + 1)}
          features={{
            fully_diluted: feat("fully_diluted"),
            anti_dilution: feat("anti_dilution"),
            transfers: feat("transfers"),
            conversions: feat("conversions"),
            corporate_actions: feat("corporate_actions"),
            founder_vesting: feat("founder_vesting"),
            waterfall: feat("waterfall"),
            demat: feat("demat"),
          }}
          showRights={feat("rights_issues")}
        />
      )}
      {tab === "fundraising" && (
        <FundraisingHub entityId={entityId} onChanged={() => setCapRefresh((x) => x + 1)} />
      )}
      {tab === "governance" && <Governance entityId={entityId} />}
      {tab === "documents" && <Documents entityId={entityId} showDataRoom={feat("dataroom")} />}
      {tab === "diligence" && <Diligence entityId={entityId} onNavigate={goTab} />}
      {tab === "compliance" && <Compliance entityId={entityId} entityType={entity.type} />}
      {["capital", "fundraise", "portfolio", "monitoring", "deals", "plan", "reports"].includes(tab) && (
        <Fund entityId={entityId} initialSub={tab} />
      )}
      {tab === "esop" && (
        <>
          <ExerciseRequests entityId={entityId} />
          <Esop entityId={entityId} />
        </>
      )}
      {tab === "valuations" && <Valuations entityId={entityId} />}
      {tab === "services" && <Services entityId={entityId} />}
      {tab === "advisors" && <Advisors entityId={entityId} />}
      {tab === "admin" && <Admin entityId={entityId} />}
      {tab === "spv" && <Spv entityId={entityId} />}
    </div>
  );
}

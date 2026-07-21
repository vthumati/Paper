import { Fragment, useEffect, useState } from "react";
import Avatar from "../components/Avatar";
import BarChart from "../components/BarChart";
import ColumnChart from "../components/ColumnChart";
import Donut from "../components/Donut";
import { uiPrompt } from "../components/Prompt";
import StrengthPie from "../components/StrengthPie";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";
import { api, type Deal, type DealCrm, type DealsImportReport } from "../api";

const STAGES = ["sourced", "screening", "diligence", "ic", "term_sheet", "invested", "passed"];
const ACT_KINDS = ["note", "meeting", "call", "email", "other"];
const ACT_ICONS: Record<string, string> = { note: "📝", meeting: "📅", call: "📞", email: "✉️", other: "🔹" };
const todayIso = () => new Date().toISOString().slice(0, 10);

// mirrors the backend STALE_DEAL_DAYS trigger (services/tasks.py)
const STALE_DEAL_DAYS = 45;
const staleDays = (d: Deal): number | null => {
  if (d.stage === "invested" || d.stage === "passed") return null;
  const since = new Date(d.stage_changed_at ?? d.created_at).getTime();
  const days = Math.floor((Date.now() - since) / 86400000);
  return days > STALE_DEAL_DAYS ? days : null;
};

/** GP-side deal flow: sourced → screening → diligence → IC → term sheet → invested,
 * with per-deal relationship intelligence (contacts + a dated activity timeline). */
export default function DealPipeline({
  fundId,
  onInvested,
}: {
  fundId: string;
  onInvested?: () => void;
}) {
  const [deals, setDeals] = useState<Deal[]>([]);
  const { error, setError, guard } = useGuard(() => load());
  const [name, setName] = useState("");
  const [sector, setSector] = useState("");
  const [amount, setAmount] = useState("");
  const [source, setSource] = useState("");

  // board | table view; board cards show each deal's contacts as avatars
  const [view, setView] = useState<"board" | "table">("board");
  const [crms, setCrms] = useState<Record<string, DealCrm>>({});

  // CSV import (onboarding an existing pipeline)
  const [impOpen, setImpOpen] = useState(false);
  const [impCsv, setImpCsv] = useState("");
  const [impName, setImpName] = useState("");
  const [impReport, setImpReport] = useState<DealsImportReport | null>(null);

  // expanded deal CRM
  const [openId, setOpenId] = useState<string | null>(null);
  const [crm, setCrm] = useState<DealCrm | null>(null);
  const [cName, setCName] = useState("");
  const [cRole, setCRole] = useState("");
  const [actKind, setActKind] = useState("note");
  const [actBody, setActBody] = useState("");
  const [actDate, setActDate] = useState(todayIso());
  const [actContact, setActContact] = useState("");

  async function load() {
    try {
      setDeals(await api.listDeals(fundId));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [fundId]);

  // board view: fetch each deal's CRM once for the contact avatar rows
  useEffect(() => {
    if (view !== "board") return;
    deals.forEach((d) => {
      if (!crms[d.id]) {
        api.dealCrm(d.id).then((r) => setCrms((m) => ({ ...m, [d.id]: r }))).catch(() => {});
      }
    });
  }, [view, deals]);

  async function toggle(id: string) {
    if (openId === id) {
      setOpenId(null);
      setCrm(null);
      return;
    }
    setOpenId(id);
    setCrm(null);
    const r = await api.dealCrm(id);
    setCrm(r);
    setCrms((m) => ({ ...m, [id]: r }));
  }

  const crmPanel = (d: Deal) =>
    !crm ? (
      <span className="muted">Loading…</span>
    ) : (
      <div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6, fontSize: 13 }}>
          <span>
            <StrengthPie value={crm.strength} /> Relationship strength{" "}
            <strong>{crm.strength}</strong>/100
          </span>
          <span className="muted">
            Follow-up: {d.next_followup_on ?? "none"}
          </span>
          <button
            className="secondary"
            style={{ flex: "0 0 auto" }}
            onClick={guard(async () => {
              const on = await uiPrompt(
                `Next follow-up on ${d.company_name} (YYYY-MM-DD, blank clears):`,
                d.next_followup_on ?? todayIso()
              );
              if (on === null) return;
              await api.setDealFollowup(d.id, on || null);
            }, "Follow-up updated")}
          >
            Set follow-up
          </button>
        </div>
        <div className="row" style={{ alignItems: "flex-start", gap: 20 }}>
        {/* contacts */}
        <div style={{ flex: 1, minWidth: 240 }}>
          <strong style={{ fontSize: 13, color: "var(--heading)" }}>Contacts</strong>
          {crm.contacts.length === 0 && <p className="muted" style={{ margin: "4px 0" }}>No contacts yet.</p>}
          {crm.contacts.map((c) => (
            <div key={c.id} style={{ fontSize: 13, margin: "3px 0" }}>
              <Avatar name={c.name} /> {c.name} <StrengthPie value={c.strength} />
              {c.role && <span className="muted"> · {c.role}</span>}
              {c.email && <span className="muted"> · {c.email}</span>}
            </div>
          ))}
          <div className="row" style={{ marginTop: 6 }}>
            <input placeholder="Name" value={cName} onChange={(e) => setCName(e.target.value)} />
            <input placeholder="Role" value={cRole} onChange={(e) => setCRole(e.target.value)} />
            <button
              style={{ flex: "0 0 auto" }}
              disabled={!cName}
              onClick={guard(async () => {
                const r = await api.addDealContact(d.id, { name: cName, role: cRole || null });
                setCrm(r); setCrms((m) => ({ ...m, [d.id]: r })); setCName(""); setCRole("");
              }, "Contact added")}
            >
              Add
            </button>
          </div>
        </div>
        {/* activity timeline */}
        <div style={{ flex: 1.4, minWidth: 280 }}>
          <strong style={{ fontSize: 13, color: "var(--heading)" }}>Activity</strong>
          {crm.activities.length === 0 && <p className="muted" style={{ margin: "4px 0" }}>No activity logged.</p>}
          {crm.activities.map((a) => (
            <div key={a.id} style={{ fontSize: 13, margin: "4px 0", borderLeft: "2px solid var(--border)", paddingLeft: 8 }}>
              <span title={a.kind}>{ACT_ICONS[a.kind] ?? ACT_ICONS.other}</span>{" "}
              <span className="badge">{a.kind}</span> <span className="muted">{a.occurred_on}</span>
              <div>{a.body}</div>
            </div>
          ))}
          <div className="row" style={{ marginTop: 6, alignItems: "flex-end" }}>
            <select value={actKind} onChange={(e) => setActKind(e.target.value)} style={{ flex: "0 0 auto", width: "auto" }}>
              {ACT_KINDS.map((k) => <option key={k} value={k}>{ACT_ICONS[k]} {k}</option>)}
            </select>
            <input type="date" value={actDate} onChange={(e) => setActDate(e.target.value)} style={{ flex: "0 0 auto", width: "auto" }} />
            {crm.contacts.length > 0 && (
              <select value={actContact} onChange={(e) => setActContact(e.target.value)} style={{ flex: "0 0 auto", width: "auto" }}>
                <option value="">— no contact —</option>
                {crm.contacts.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            )}
            <input placeholder="What happened?" value={actBody} onChange={(e) => setActBody(e.target.value)} />
            <button
              style={{ flex: "0 0 auto" }}
              disabled={!actBody}
              onClick={guard(async () => {
                const r = await api.addDealActivity(d.id, {
                  kind: actKind,
                  body: actBody,
                  occurred_on: actDate,
                  contact_id: actContact || null,
                });
                setCrm(r); setCrms((m) => ({ ...m, [d.id]: r })); setActBody("");
              }, "Activity logged")}
            >
              Log
            </button>
          </div>
        </div>
        </div>
      </div>
    );

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        Deal pipeline
        <span style={{ marginLeft: "auto", display: "flex", gap: 4 }}>
          <button className="secondary" onClick={() => setImpOpen((v) => !v)}>
            {impOpen ? "Close import" : "Import CSV"}
          </button>
          <button className={view === "board" ? "" : "secondary"} onClick={() => setView("board")}>Board</button>
          <button className={view === "table" ? "" : "secondary"} onClick={() => setView("table")}>Table</button>
        </span>
      </h3>
      {error && <p className="error">{error}</p>}

      {impOpen && (
        <div style={{ margin: "8px 0 12px" }}>
          <p className="muted" style={{ margin: "0 0 6px" }}>
            Onboard an existing pipeline from a spreadsheet — columns: company_name (required),
            sector, stage, amount, source.{" "}
            <a href="#" onClick={(e) => { e.preventDefault(); api.downloadDealsTemplate(fundId); }}>
              Download the template
            </a>
            .
          </p>
          <div className="row" style={{ alignItems: "center" }}>
            <input
              type="file"
              accept=".csv,text/csv"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                const reader = new FileReader();
                reader.onload = () => {
                  setImpCsv(String(reader.result ?? ""));
                  setImpName(f.name);
                  setImpReport(null);
                };
                reader.readAsText(f);
              }}
            />
            <button
              style={{ flex: "0 0 auto" }}
              disabled={!impCsv}
              onClick={guard(async () => setImpReport(await api.importDeals(fundId, impCsv, false)))}
            >
              Validate
            </button>
            <button
              style={{ flex: "0 0 auto" }}
              disabled={!impCsv || !impReport?.valid || impReport?.applied}
              onClick={guard(async () => {
                setImpReport(await api.importDeals(fundId, impCsv, true));
              }, "Deals imported")}
            >
              Apply import
            </button>
          </div>
          {impName && <p className="muted" style={{ margin: "4px 0 0" }}>{impName}</p>}
          {impReport && !impReport.valid && (
            <ul className="muted" style={{ margin: "6px 0 0" }}>
              {impReport.errors.map((e, i) => <li key={i} className="error">{e}</li>)}
            </ul>
          )}
          {impReport?.valid && (
            <p className={impReport.applied ? "" : "muted"} style={{ margin: "6px 0 0" }}>
              {impReport.applied
                ? `Imported ${impReport.imported} deal(s) ✓`
                : `Ready to import ${impReport.rows} deal(s).`}
            </p>
          )}
        </div>
      )}
      <div className="row">
        <input placeholder="Company" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="Sector" value={sector} onChange={(e) => setSector(e.target.value)} />
        <input placeholder="Cheque ₹" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <input placeholder="Source (who referred it)" value={source} onChange={(e) => setSource(e.target.value)} />
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!name}
          onClick={guard(async () => {
            await api.createDeal(fundId, {
              company_name: name,
              sector: sector || null,
              amount: amount || "0",
              source: source || null,
            });
            setName(""); setSector(""); setAmount(""); setSource("");
          })}
        >
          Add deal
        </button>
      </div>
      {view === "board" && deals.length > 0 && (
        <>
          <div className="kanban">
            {STAGES.map((s) => {
              const inStage = deals.filter((d) => d.stage === s);
              return (
                <div key={s} className="kanban-col" style={s === "passed" ? { opacity: 0.65 } : undefined}>
                  <div className="kanban-col-title">
                    <span>{s.replace(/_/g, " ")}</span>
                    <span className="muted">{inStage.length}</span>
                  </div>
                  {inStage.map((d) => (
                    <div key={d.id} className="deal-card">
                      <strong>{d.company_name}</strong>
                      {d.next_followup_on && d.next_followup_on < todayIso() && d.stage !== "invested" && d.stage !== "passed" && (
                        <span className="badge danger" title={`Follow-up was due ${d.next_followup_on}`} style={{ marginLeft: 5 }}>
                          🔔 overdue
                        </span>
                      )}
                      {staleDays(d) !== null && (
                        <span className="badge active" title={`No stage movement for ${staleDays(d)} days (over ${STALE_DEAL_DAYS})`} style={{ marginLeft: 5 }}>
                          stale {staleDays(d)}d
                        </span>
                      )}
                      {d.sector && (
                        <div style={{ margin: "4px 0" }}><span className="badge">{d.sector}</span></div>
                      )}
                      <div style={{ margin: "2px 0" }}>{fmtMoney(d.amount)}</div>
                      {(crms[d.id]?.contacts.length ?? 0) > 0 && (
                        <div style={{ margin: "4px 0" }}>
                          {crms[d.id].contacts.slice(0, 4).map((c) => (
                            <Avatar key={c.id} name={c.name} />
                          ))}
                        </div>
                      )}
                      {d.stage === "invested" ? (
                        <span className="badge complete">invested</span>
                      ) : (
                        <select
                          value={d.stage}
                          onChange={(ev) => guard(() => api.setDealStage(d.id, ev.target.value))()}
                        >
                          {STAGES.filter((x) => x !== "invested").map((x) => (
                            <option key={x} value={x}>{x}</option>
                          ))}
                        </select>
                      )}
                      <div style={{ marginTop: 6, display: "flex", gap: 4 }}>
                        <button className="secondary" onClick={() => toggle(d.id)}>
                          {openId === d.id ? "Hide" : "CRM"}
                        </button>
                        {d.stage !== "invested" && d.stage !== "passed" && (
                          <button
                            className="secondary"
                            onClick={guard(async () => {
                              const pct = await uiPrompt(`Ownership % acquired in ${d.company_name}:`, "10");
                              await api.investDeal(d.id, { ownership_pct: pct || "0" });
                              onInvested?.();
                            })}
                          >
                            Invest
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })}
          </div>
          {openId && (() => {
            const d = deals.find((x) => x.id === openId);
            if (!d) return null;
            return (
              <div style={{ marginTop: 10, background: "var(--light)", borderRadius: 10, padding: 12 }}>
                <strong style={{ fontSize: 13, color: "var(--heading)" }}>{d.company_name} — CRM</strong>
                <div style={{ marginTop: 6 }}>{crmPanel(d)}</div>
              </div>
            );
          })()}
        </>
      )}

      {view === "table" && deals.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Company</th><th>Sector</th><th>Cheque</th><th>Stage</th><th></th><th></th></tr>
          </thead>
          <tbody>
            {deals.map((d) => (
              <Fragment key={d.id}>
                <tr>
                  <td>
                    {d.company_name}
                    {d.next_followup_on && d.next_followup_on < todayIso() && d.stage !== "invested" && d.stage !== "passed" && (
                      <span className="badge danger" title={`Follow-up was due ${d.next_followup_on}`} style={{ marginLeft: 5 }}>
                        🔔
                      </span>
                    )}
                    {staleDays(d) !== null && (
                      <span className="badge active" title={`No stage movement for ${staleDays(d)} days (over ${STALE_DEAL_DAYS})`} style={{ marginLeft: 5 }}>
                        stale
                      </span>
                    )}
                  </td>
                  <td>{d.sector ?? "—"}</td>
                  <td>{fmtMoney(d.amount)}</td>
                  <td>
                    {d.stage === "invested" ? (
                      <span className="badge complete">invested</span>
                    ) : (
                      <select
                        value={d.stage}
                        onChange={(ev) => guard(() => api.setDealStage(d.id, ev.target.value))()}
                      >
                        {STAGES.filter((s) => s !== "invested").map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td>
                    <button className="secondary" onClick={() => toggle(d.id)}>
                      {openId === d.id ? "Hide" : "CRM"}
                    </button>
                  </td>
                  <td>
                    {d.stage !== "invested" && d.stage !== "passed" && (
                      <button
                        className="secondary"
                        onClick={guard(async () => {
                          const pct = await uiPrompt(`Ownership % acquired in ${d.company_name}:`, "10");
                          await api.investDeal(d.id, { ownership_pct: pct || "0" });
                          onInvested?.();
                        })}
                      >
                        Invest
                      </button>
                    )}
                  </td>
                </tr>
                {openId === d.id && (
                  <tr>
                    <td colSpan={6} style={{ background: "var(--light)" }}>{crmPanel(d)}</td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}

      {deals.length > 1 && (
        <div style={{ marginTop: 18 }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>
            Pipeline analytics — current snapshot
          </div>
          <div className="row" style={{ alignItems: "flex-start", gap: 26 }}>
            <div style={{ flex: 1.4, minWidth: 300 }}>
              <strong style={{ fontSize: 13, color: "var(--heading)" }}>Deals by stage</strong>
              <div style={{ marginTop: 8 }}>
                <ColumnChart
                  height={120}
                  format={(v) => fmtMoney(v)}
                  columns={STAGES.filter((s) => deals.some((d) => d.stage === s)).map((s) => {
                    const inStage = deals.filter((d) => d.stage === s);
                    return {
                      label: `${s.replace(/_/g, " ")} (${inStage.length})`,
                      segments: [
                        {
                          label: "Cheque value",
                          value: inStage.reduce((sum, d) => sum + Number(d.amount), 0),
                          color: "#2f6b52",
                        },
                      ],
                    };
                  })}
                />
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 210 }}>
              <strong style={{ fontSize: 13, color: "var(--heading)" }}>By sector</strong>
              <div style={{ marginTop: 8 }}>
                <Donut
                  size={130}
                  segments={Object.entries(
                    deals.reduce<Record<string, number>>((m, d) => {
                      const k = d.sector || "unspecified";
                      m[k] = (m[k] ?? 0) + 1;
                      return m;
                    }, {})
                  ).map(([label, value]) => ({ label, value }))}
                />
              </div>
            </div>
            {deals.some((d) => d.source) && (
              <div style={{ flex: 1.2, minWidth: 260 }}>
                <strong style={{ fontSize: 13, color: "var(--heading)" }}>Top deal sources</strong>
                <div style={{ marginTop: 8 }}>
                  <BarChart
                    bars={Object.entries(
                      deals.reduce<Record<string, number>>((m, d) => {
                        if (d.source) m[d.source] = (m[d.source] ?? 0) + 1;
                        return m;
                      }, {})
                    )
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 5)
                      .map(([label, value]) => ({
                        label,
                        value,
                        display: `${value} deal${value === 1 ? "" : "s"}`,
                      }))}
                  />
                </div>
              </div>
            )}
            {deals.some((d) => d.stage !== "invested" && d.stage !== "passed" && Number(d.amount) > 0) && (
              <div style={{ flex: 1.2, minWidth: 260 }}>
                <strong style={{ fontSize: 13, color: "var(--heading)" }}>Top active deals</strong>
                <div style={{ marginTop: 8 }}>
                  <BarChart
                    bars={deals
                      .filter((d) => d.stage !== "invested" && d.stage !== "passed" && Number(d.amount) > 0)
                      .sort((a, b) => Number(b.amount) - Number(a.amount))
                      .slice(0, 5)
                      .map((d) => ({
                        label: d.company_name,
                        value: Number(d.amount),
                        display: fmtMoney(d.amount),
                      }))}
                  />
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

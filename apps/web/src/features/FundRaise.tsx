import { Fragment, useEffect, useState } from "react";
import { api, type FundraiseSummary, type ProspectCrm } from "../api";
import { uiPrompt } from "../components/Prompt";
import StrengthPie from "../components/StrengthPie";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";
import EmptyState from "../components/EmptyState";
import Stat from "../components/Stat";

const KINDS: Record<string, string> = {
  institutional: "Institutional",
  family_office: "Family office",
  hni: "HNI",
  fof: "Fund of funds",
};
// stages selectable in the pipeline; "committed" is reached by converting
const STAGES = ["prospect", "contacted", "meeting", "diligence", "soft_circled", "passed"];
const STAGE_ORDER = ["prospect", "contacted", "meeting", "diligence", "soft_circled", "committed", "passed"];
export const STAGE_COLORS: Record<string, string> = {
  prospect: "#8a8f98",
  contacted: "#c9a227",
  meeting: "#2f6fb2",
  diligence: "#7b5cd6",
  soft_circled: "#2f7d5b",
  committed: "#1e6b3f",
  passed: "#b3423a",
};
const ACT_KINDS = ["note", "meeting", "call", "email", "other"];
const ACT_ICONS: Record<string, string> = { note: "📝", meeting: "📅", call: "📞", email: "✉️", other: "🔹" };
const todayIso = () => new Date().toISOString().slice(0, 10);

/** LP-fundraising CRM (FR-J-16): the GP's pipeline for raising the fund from
 * prospective LPs — prospect → soft-circled → committed. Converting a won
 * prospect creates an LP with a commitment. Distinct from the deal pipeline. */
export default function FundRaise({ fundId, onChanged }: { fundId: string; onChanged?: () => void }) {
  const [sum, setSum] = useState<FundraiseSummary | null>(null);
  const [open, setOpen] = useState(false);
  const { error, guard } = useGuard(async () => {
    await load();
    onChanged?.();
  });

  const [name, setName] = useState("");
  const [firm, setFirm] = useState("");
  const [kind, setKind] = useState("institutional");
  const [target, setTarget] = useState("");

  // expanded prospect CRM (mirrors the deal pipeline's relationship panel)
  const [openId, setOpenId] = useState<string | null>(null);
  const [crm, setCrm] = useState<ProspectCrm | null>(null);
  const [actKind, setActKind] = useState("note");
  const [actBody, setActBody] = useState("");
  const [actDate, setActDate] = useState(todayIso());

  async function toggleCrm(pid: string) {
    if (openId === pid) {
      setOpenId(null);
      setCrm(null);
      return;
    }
    setOpenId(pid);
    setCrm(null);
    setCrm(await api.prospectCrm(fundId, pid));
  }

  const load = () => api.fundraiseSummary(fundId).then(setSum);
  useEffect(() => {
    load();
  }, [fundId]);

  if (!sum) return null;
  const progress = Math.min(Math.max(sum.progress_pct ?? 0, 0), 100);

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>🎯</span> Fund raise — LP pipeline
        <button className="secondary" style={{ marginLeft: "auto" }} onClick={() => setOpen((v) => !v)}>
          {open ? "Close" : "Add prospect"}
        </button>
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Track prospective LPs from first contact to commitment. Converting a soft-circled prospect
        creates an LP with their commitment.
      </p>
      {error && <p className="error">{error}</p>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <Stat label="Committed" value={fmtMoney(sum.committed)} hint="Actual committed LP capital (converted prospects)" />
        <Stat label="Target corpus" value={fmtMoney(sum.target_corpus)} />
        <Stat label="Soft-circled" value={fmtMoney(sum.soft_circled)} hint="Target cheques of prospects at the soft-circled stage" />
        <Stat label="Active pipeline" value={fmtMoney(sum.pipeline)} hint="Target cheques of all prospects not yet committed or passed" />
      </div>

      {Number(sum.target_corpus) > 0 && (
        <div style={{ margin: "12px 0 4px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
            <span className="muted">Committed vs target corpus</span>
            <span className="num" style={{ color: "var(--muted)" }}>{sum.progress_pct ?? 0}%</span>
          </div>
          <div style={{ height: 10, background: "var(--light)", borderRadius: 6, overflow: "hidden", marginTop: 5 }}>
            <div style={{ width: `${progress}%`, height: "100%", background: "var(--ok, #2f7d5b)", borderRadius: 6 }} />
          </div>
        </div>
      )}

      {Object.keys(sum.by_stage).length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8 }}>
          {STAGE_ORDER.filter((s) => sum.by_stage[s]).map((s) => (
            <span key={s} className="badge" style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
              <span style={{ width: 8, height: 8, borderRadius: "50%", background: STAGE_COLORS[s] ?? "#8a8f98" }} />
              {s.replace(/_/g, " ")} · {fmtMoney(sum.by_stage[s].target)}{" "}
              <span className="muted">({sum.by_stage[s].count})</span>
            </span>
          ))}
        </div>
      )}

      {open && (
        <div className="row" style={{ alignItems: "flex-end", marginTop: 12 }}>
          <div><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><label>Firm</label><input value={firm} onChange={(e) => setFirm(e.target.value)} /></div>
          <div>
            <label>Type</label>
            <select value={kind} onChange={(e) => setKind(e.target.value)}>
              {Object.entries(KINDS).map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </div>
          <div><label>Target cheque (₹)</label><input value={target} onChange={(e) => setTarget(e.target.value)} /></div>
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!name}
            onClick={guard(async () => {
              await api.addLpProspect(fundId, {
                name, firm: firm || null, kind, target_commitment: target || "0",
              });
              setName(""); setFirm(""); setTarget("");
            }, "Prospect added")}
          >
            Add prospect
          </button>
        </div>
      )}

      {sum.prospects.length === 0 ? (
        <EmptyState icon="🎯" title="No prospects yet" hint="Add prospective LPs above and move them through the pipeline toward a commitment." />
      ) : (
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr><th>Prospect</th><th>Firm</th><th>Type</th><th>Target</th><th>Stage</th><th></th></tr>
          </thead>
          <tbody>
            {sum.prospects.map((p) => (
              <Fragment key={p.id}>
                <tr>
                  <td>
                    {p.name}
                    {p.next_followup_on && p.next_followup_on < todayIso() && !p.lp_id && p.stage !== "passed" && (
                      <span className="badge danger" title={`Follow-up was due ${p.next_followup_on}`} style={{ marginLeft: 5 }}>
                        🔔
                      </span>
                    )}
                  </td>
                  <td>{p.firm || <span className="muted">—</span>}</td>
                  <td>{KINDS[p.kind] ?? p.kind}</td>
                  <td>{fmtMoney(p.target_commitment)}</td>
                  <td>
                    {p.lp_id ? (
                      <span className="badge complete">committed</span>
                    ) : (
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                        <span style={{ width: 8, height: 8, borderRadius: "50%", flex: "0 0 auto", background: STAGE_COLORS[p.stage] ?? "#8a8f98" }} />
                        <select
                          value={p.stage}
                          onChange={(e) => guard(() => api.setLpProspectStage(fundId, p.id, e.target.value))()}
                        >
                          {STAGES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                        </select>
                      </span>
                    )}
                  </td>
                  <td>
                    <button className="secondary" onClick={() => toggleCrm(p.id)}>
                      {openId === p.id ? "Hide" : "CRM"}
                    </button>{" "}
                    {p.lp_id ? (
                      <span className="badge">LP</span>
                    ) : (
                      <button
                        className="secondary"
                        title="Create an LP from this prospect with their target cheque as the commitment"
                        onClick={guard(async () => {
                          await api.convertLpProspect(fundId, p.id, p.target_commitment);
                        }, `${p.name} converted to an LP`)}
                      >
                        Convert to LP
                      </button>
                    )}
                  </td>
                </tr>
                {openId === p.id && (
                  <tr>
                    <td colSpan={6} style={{ background: "var(--light)" }}>
                      {!crm ? (
                        <span className="muted">Loading…</span>
                      ) : (
                        <div>
                          <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6, fontSize: 13 }}>
                            <span>
                              <StrengthPie value={crm.strength} /> Relationship strength{" "}
                              <strong>{crm.strength}</strong>/100
                            </span>
                            <span className="muted">Follow-up: {p.next_followup_on ?? "none"}</span>
                            <button
                              className="secondary"
                              style={{ flex: "0 0 auto" }}
                              onClick={guard(async () => {
                                const on = await uiPrompt(
                                  `Next follow-up with ${p.name} (YYYY-MM-DD, blank clears):`,
                                  p.next_followup_on ?? todayIso()
                                );
                                if (on === null) return;
                                setSum(await api.setProspectFollowup(fundId, p.id, on || null));
                              }, "Follow-up updated")}
                            >
                              Set follow-up
                            </button>
                          </div>
                          {crm.activities.length === 0 && (
                            <p className="muted" style={{ margin: "4px 0" }}>No touchpoints logged yet.</p>
                          )}
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
                            <input placeholder="What happened?" value={actBody} onChange={(e) => setActBody(e.target.value)} />
                            <button
                              style={{ flex: "0 0 auto" }}
                              disabled={!actBody}
                              onClick={guard(async () => {
                                const r = await api.addProspectActivity(fundId, p.id, {
                                  kind: actKind, body: actBody, occurred_on: actDate,
                                });
                                setCrm(r); setActBody("");
                              }, "Touchpoint logged")}
                            >
                              Log
                            </button>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

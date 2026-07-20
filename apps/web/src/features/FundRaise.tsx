import { useEffect, useState } from "react";
import { api, type FundraiseSummary } from "../api";
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
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.firm || <span className="muted">—</span>}</td>
                <td>{KINDS[p.kind] ?? p.kind}</td>
                <td>{fmtMoney(p.target_commitment)}</td>
                <td>
                  {p.lp_id ? (
                    <span className="badge complete">committed</span>
                  ) : (
                    <select
                      value={p.stage}
                      onChange={(e) => guard(() => api.setLpProspectStage(fundId, p.id, e.target.value))()}
                    >
                      {STAGES.map((s) => <option key={s} value={s}>{s.replace("_", " ")}</option>)}
                    </select>
                  )}
                </td>
                <td>
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
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

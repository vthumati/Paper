import { useEffect, useState } from "react";
import { fmtMoney } from "../lib/format";
import { useGuard } from "../hooks";
import { api, type Prospect, type Round } from "../api";
import PageHeader from "../components/PageHeader";

const STAGES = ["contacted", "meeting", "diligence", "term_sheet", "committed", "passed"];
const STAGE_COLORS: Record<string, string> = {
  contacted: "#c9a227",
  meeting: "#2f6fb2",
  diligence: "#7b5cd6",
  term_sheet: "#2f7d5b",
  committed: "#1e6b3f",
  passed: "#b3423a",
};
const label = (s: string) => s.replace(/_/g, " ");

export default function Pipeline({
  entityId,
  onChanged,
}: {
  entityId: string;
  onChanged?: () => void;
}) {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [rounds, setRounds] = useState<Round[]>([]);
  const [summary, setSummary] = useState<{
    by_stage: Record<string, { count: number; value: string }>;
    open_value: string;
    committed_value: string;
    total: number;
  } | null>(null);
  const { error, setError, guard } = useGuard(() => load());
  const [note, setNote] = useState("");
  const [view, setView] = useState<"board" | "table">("board");
  const [dragId, setDragId] = useState<string | null>(null);
  const [overStage, setOverStage] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [firm, setFirm] = useState("");
  const [check, setCheck] = useState("");
  const [roundId, setRoundId] = useState("");

  async function load() {
    try {
      const [p, r, s] = await Promise.all([
        api.listPipeline(entityId),
        api.listRounds(entityId),
        api.pipelineSummary(entityId),
      ]);
      setProspects(p);
      setRounds(r);
      setSummary(s);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  const moveStage = (p: Prospect, stage: string) => {
    if (p.commitment_id || p.stage === stage) return;
    guard(() => api.updateProspectStage(p.id, { stage }))();
  };

  const convert = (p: Prospect) =>
    guard(async () => {
      await api.convertProspect(p.id);
      setNote(`${p.name} converted to a round commitment.`);
      onChanged?.();
    })();

  const roundName = (id: string | null) =>
    id ? rounds.find((r) => r.id === id)?.name : null;

  const card = (p: Prospect) => (
    <div
      key={p.id}
      className="deal-card"
      draggable={!p.commitment_id}
      onDragStart={(e) => {
        setDragId(p.id);
        e.dataTransfer.effectAllowed = "move";
        try {
          e.dataTransfer.setData("text/plain", p.id);
        } catch {
          /* some browsers restrict setData outside user gesture */
        }
      }}
      onDragEnd={() => {
        setDragId(null);
        setOverStage(null);
      }}
      style={{ cursor: p.commitment_id ? "default" : "grab" }}
    >
      <strong>{p.name}</strong>
      {p.firm && <div className="muted" style={{ fontSize: 12 }}>{p.firm}</div>}
      {p.check_size && <div style={{ margin: "2px 0" }}>{fmtMoney(p.check_size)}</div>}
      {roundName(p.round_id) && (
        <div style={{ margin: "2px 0" }}>
          <span className="badge">{roundName(p.round_id)}</span>
        </div>
      )}
      {p.commitment_id ? (
        <span className="badge complete">committed → round</span>
      ) : p.round_id && p.check_size ? (
        <button className="secondary" style={{ marginTop: 4 }} onClick={() => convert(p)}>
          Convert to commitment
        </button>
      ) : (
        <span className="muted" style={{ fontSize: 11 }}>
          link a round + check size to convert
        </span>
      )}
    </div>
  );

  return (
    <div className="card">
      <PageHeader
        icon="📇"
        title="Fundraising pipeline"
        subtitle="Investor CRM — drag prospects from first contact to commitment"
        right={
          <>
            <button className={view === "board" ? "" : "secondary"} onClick={() => setView("board")}>
              Board
            </button>{" "}
            <button className={view === "table" ? "" : "secondary"} onClick={() => setView("table")}>
              Table
            </button>
          </>
        }
      />
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}
      {summary && (
        <p className="muted">
          {summary.total} prospects · Open value {fmtMoney(summary.open_value)} · Committed {fmtMoney(summary.committed_value)}
        </p>
      )}

      <div className="row">
        <input placeholder="Investor / fund" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="Firm" value={firm} onChange={(e) => setFirm(e.target.value)} />
        <input placeholder="Check size ₹" value={check} onChange={(e) => setCheck(e.target.value)} />
        <select value={roundId} onChange={(e) => setRoundId(e.target.value)}>
          <option value="">no round</option>
          {rounds.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </select>
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!name}
          onClick={guard(async () => {
            await api.addProspect(entityId, {
              name,
              firm: firm || null,
              check_size: check || null,
              round_id: roundId || null,
            });
            setName(""); setFirm(""); setCheck("");
          })}
        >
          Add prospect
        </button>
      </div>

      {prospects.length === 0 ? (
        <p className="muted" style={{ marginTop: 12 }}>
          No prospects yet — add the investors you're raising from above.
        </p>
      ) : view === "board" ? (
        <div className="kanban">
          {STAGES.map((s) => {
            const inStage = prospects.filter((p) => p.stage === s);
            const value = summary?.by_stage?.[s]?.value;
            return (
              <div
                key={s}
                className="kanban-col"
                style={{
                  ...(s === "passed" ? { opacity: 0.7 } : {}),
                  outline: overStage === s && dragId ? "2px dashed var(--accent)" : "none",
                }}
                onDragOver={(e) => {
                  if (dragId) {
                    e.preventDefault();
                    setOverStage(s);
                  }
                }}
                onDragLeave={() => setOverStage((cur) => (cur === s ? null : cur))}
                onDrop={() => {
                  const p = prospects.find((x) => x.id === dragId);
                  if (p) moveStage(p, s);
                  setDragId(null);
                  setOverStage(null);
                }}
              >
                <div className="kanban-col-title">
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 5 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", background: STAGE_COLORS[s] }} />
                    {label(s)}
                  </span>
                  <span className="muted">
                    {inStage.length}
                    {value && Number(value) > 0 ? ` · ${fmtMoney(value)}` : ""}
                  </span>
                </div>
                {inStage.map(card)}
              </div>
            );
          })}
        </div>
      ) : (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Investor</th><th>Firm</th><th>Check (₹)</th><th>Stage</th><th></th></tr>
          </thead>
          <tbody>
            {prospects.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.firm || "—"}</td>
                <td>{p.check_size ? fmtMoney(p.check_size) : "—"}</td>
                <td>
                  <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                    <span style={{ width: 8, height: 8, borderRadius: "50%", flex: "0 0 auto", background: STAGE_COLORS[p.stage] ?? "#8a8f98" }} />
                    <select
                      value={p.stage}
                      disabled={!!p.commitment_id}
                      onChange={(ev) => guard(() => api.updateProspectStage(p.id, { stage: ev.target.value }))()}
                    >
                      {STAGES.map((s) => <option key={s} value={s}>{label(s)}</option>)}
                    </select>
                  </span>
                </td>
                <td>
                  {p.commitment_id ? (
                    <span className="badge complete">committed →round</span>
                  ) : p.round_id && p.check_size ? (
                    <button className="secondary" onClick={() => convert(p)}>
                      Convert to commitment
                    </button>
                  ) : (
                    <span className="muted">link a round + check size to convert</span>
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

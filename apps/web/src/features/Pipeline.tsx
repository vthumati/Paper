import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import { api, type Prospect, type Round } from "../api";

const STAGES = ["contacted", "meeting", "diligence", "term_sheet", "committed", "passed"];

export default function Pipeline({
  entityId,
  onChanged,
}: {
  entityId: string;
  onChanged?: () => void;
}) {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [rounds, setRounds] = useState<Round[]>([]);
  const [summary, setSummary] = useState<{ open_value: string; committed_value: string; total: number } | null>(null);
  const { error, setError, guard } = useGuard(() => load());
  const [note, setNote] = useState("");

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

  return (
    <div className="card">
      <h3>Fundraising pipeline (investor CRM)</h3>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}
      {summary && (
        <p className="muted">
          {summary.total} prospects · Open value ₹{summary.open_value} · Committed ₹{summary.committed_value}
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

      {prospects.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Investor</th><th>Firm</th><th>Check (₹)</th><th>Stage</th><th></th></tr>
          </thead>
          <tbody>
            {prospects.map((p) => (
              <tr key={p.id}>
                <td>{p.name}</td>
                <td>{p.firm || "—"}</td>
                <td>{p.check_size || "—"}</td>
                <td>
                  <select
                    value={p.stage}
                    disabled={!!p.commitment_id}
                    onChange={(ev) => guard(() => api.updateProspectStage(p.id, { stage: ev.target.value }))()}
                  >
                    {STAGES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
                  </select>
                </td>
                <td>
                  {p.commitment_id ? (
                    <span className="badge complete">committed →round</span>
                  ) : p.round_id && p.check_size ? (
                    <button
                      className="secondary"
                      onClick={guard(async () => {
                        await api.convertProspect(p.id);
                        setNote(`${p.name} converted to a round commitment.`);
                        onChanged?.();
                      })}
                    >
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

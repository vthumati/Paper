import { useEffect, useState } from "react";
import { api, type Obligation } from "../api";
import ProgressRing from "../components/ProgressRing";

const STATUSES = ["due", "in_prep", "filed", "acknowledged"];

export default function Compliance({
  entityId,
  entityType,
}: {
  entityId: string;
  entityType?: string;
}) {
  const [obs, setObs] = useState<Obligation[]>([]);
  const [health, setHealth] = useState<{ total: number; filed: number; overdue: number; score: number } | null>(null);
  const [fyEnd, setFyEnd] = useState("2026-03-31");
  const [error, setError] = useState("");

  const load = async () => {
    try {
      setObs(await api.listCompliance(entityId));
      setHealth(await api.complianceHealth(entityId));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    load();
  }, [entityId]);

  async function generate() {
    setError("");
    try {
      await api.generateCompliance(entityId, { financial_year_end: fyEnd });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function generatePeriodic() {
    setError("");
    try {
      await api.generatePeriodicCompliance(entityId, { financial_year_end: fyEnd });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function generateAif() {
    setError("");
    try {
      await api.generateAifCompliance(entityId, { financial_year_end: fyEnd });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function setStatus(id: string, status: string) {
    setError("");
    try {
      await api.updateObligation(id, { status });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>Compliance calendar</h2>
        <p className="muted">
          Generate statutory ROC obligations from the financial-year end (assumes a 31-March FY).
        </p>
        <div className="row">
          <div style={{ flex: "0 0 200px" }}>
            <label>Financial year end</label>
            <input type="date" value={fyEnd} onChange={(e) => setFyEnd(e.target.value)} />
          </div>
          <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
            <button onClick={generate}>Generate annual ROC</button>
          </div>
          <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
            <button className="secondary" onClick={generatePeriodic}>Generate GST/TDS schedule</button>
          </div>
          {(entityType === "fund" || entityType === "spv") && (
            <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
              <button className="secondary" onClick={generateAif}>Generate SEBI AIF calendar</button>
            </div>
          )}
          <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
            <button className="secondary" onClick={() => api.downloadComplianceCsv(entityId)}>Export CSV</button>
          </div>
        </div>
        {health && health.total > 0 && (
          <div className="row" style={{ alignItems: "center", gap: 20, marginTop: 10 }}>
            <ProgressRing value={health.score} label="compliance health" size={110} />
            <p className="muted">
              {health.filed}/{health.total} filed ·{" "}
              {health.overdue > 0 ? (
                <span className="badge active">{health.overdue} overdue</span>
              ) : (
                <span className="badge complete">none overdue</span>
              )}
            </p>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Obligations</h3>
        {obs.length === 0 ? (
          <p className="muted">None yet — generate the calendar above.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Form</th>
                <th>Title</th>
                <th>Category</th>
                <th>Period</th>
                <th>Due</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {obs.map((o) => (
                <tr key={o.id}>
                  <td>{o.form_code}</td>
                  <td>{o.title}</td>
                  <td>{o.category}</td>
                  <td>{o.period_label}</td>
                  <td>
                    {o.due_date}{" "}
                    {o.overdue && <span className="badge active">overdue</span>}
                  </td>
                  <td>
                    <select value={o.status} onChange={(e) => setStatus(o.id, e.target.value)}>
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, type CurrentFmv, type Valuation } from "../api";

const METHODS = [
  { v: "rule_11ua", label: "Rule 11UA (Income-Tax)" },
  { v: "fema", label: "FEMA pricing" },
  { v: "fair_value", label: "Fair value (ESOP)" },
];

export default function Valuations({ entityId }: { entityId: string }) {
  const [vals, setVals] = useState<Valuation[]>([]);
  const [current, setCurrent] = useState<CurrentFmv | null>(null);
  const [error, setError] = useState("");

  const [method, setMethod] = useState("rule_11ua");
  const [fmv, setFmv] = useState("");
  const [date, setDate] = useState("2026-04-01");
  const [valuer, setValuer] = useState("");

  async function load() {
    try {
      const [v, c] = await Promise.all([
        api.listValuations(entityId),
        api.currentValuation(entityId),
      ]);
      setVals(v);
      setCurrent(c);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  async function create() {
    setError("");
    try {
      await api.createValuation(entityId, {
        method,
        fmv_per_share: fmv,
        valuation_date: date,
        valuer_name: valuer || null,
      });
      setFmv("");
      setValuer("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>Valuations</h2>
        <p className="muted">
          Current FMV:{" "}
          {current?.fmv_per_share ? (
            <strong>
              ₹{current.fmv_per_share} (as of {current.valuation_date})
            </strong>
          ) : (
            <em>none on record — ESOP perquisite will use the value entered at exercise.</em>
          )}
        </p>
      </div>

      <div className="card">
        <h3>Record valuation</h3>
        <div className="row">
          <div>
            <label>Method</label>
            <select value={method} onChange={(e) => setMethod(e.target.value)}>
              {METHODS.map((m) => (
                <option key={m.v} value={m.v}>{m.label}</option>
              ))}
            </select>
          </div>
          <div>
            <label>FMV per share (₹)</label>
            <input value={fmv} onChange={(e) => setFmv(e.target.value)} />
          </div>
          <div>
            <label>Valuation date</label>
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} />
          </div>
          <div>
            <label>Valuer / merchant banker</label>
            <input value={valuer} onChange={(e) => setValuer(e.target.value)} />
          </div>
        </div>
        <div style={{ marginTop: 10 }}>
          <button disabled={!fmv} onClick={create}>
            Record valuation
          </button>
        </div>
      </div>

      <div className="card">
        <h3>History</h3>
        {vals.length === 0 ? (
          <p className="muted">No valuations yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Method</th>
                <th>FMV/share</th>
                <th>Valuer</th>
                <th>Valid until</th>
              </tr>
            </thead>
            <tbody>
              {vals.map((v) => (
                <tr key={v.id}>
                  <td>{v.valuation_date}</td>
                  <td>{v.method}</td>
                  <td>₹{v.fmv_per_share}</td>
                  <td>{v.valuer_name || "—"}</td>
                  <td>{v.valid_until || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

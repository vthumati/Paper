import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { toast } from "../components/Toast";
import { api, type CurrentFmv, type Valuation, type ValuationEstimate } from "../api";
import LineChart from "../components/LineChart";
import StartupValuation from "./StartupValuation";

const METHODS = [
  { v: "rule_11ua", label: "Rule 11UA (Income-Tax)" },
  { v: "fema", label: "FEMA pricing" },
  { v: "fair_value", label: "Fair value (ESOP)" },
];

const SUBTABS = [
  { key: "reports", label: "Reports & FMV" },
  { key: "estimate", label: "Indicative estimate" },
] as const;
type SubTab = (typeof SUBTABS)[number]["key"];

export default function Valuations({ entityId }: { entityId: string }) {
  const [sub, setSub] = useState<SubTab>("reports");
  const [vals, setVals] = useState<Valuation[]>([]);
  const [current, setCurrent] = useState<CurrentFmv | null>(null);
  const [estimates, setEstimates] = useState<ValuationEstimate[]>([]);
  const [error, setError] = useState("");

  const [method, setMethod] = useState("rule_11ua");
  const [fmv, setFmv] = useState("");
  const [date, setDate] = useState("2026-04-01");
  const [valuer, setValuer] = useState("");

  async function load() {
    try {
      const [v, c, e] = await Promise.all([
        api.listValuations(entityId),
        api.currentValuation(entityId),
        api.listValuationEstimates(entityId).catch(() => []),
      ]);
      setVals(v);
      setCurrent(c);
      setEstimates(e);
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
      toast("Valuation recorded");
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // FMV history (registered valuations) + indicative per-share estimates as a
  // second series, both plotted over time.
  const fmvSeries = {
    label: "Registered FMV",
    color: "#2f6b52",
    points: vals
      .filter((v) => v.status === "final")
      .map((v) => ({ x: v.valuation_date, y: Number(v.fmv_per_share) })),
  };
  const estSeries = {
    label: "Indicative (self-serve)",
    color: "#c9a227",
    points: estimates
      .filter((e) => e.results.per_share)
      .map((e) => ({ x: e.created_at.slice(0, 10), y: Number(e.results.per_share) })),
  };
  const hasChart = fmvSeries.points.length + estSeries.points.length > 0;

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="tabs subtabs">
        {SUBTABS.map((t) => (
          <button key={t.key} className={sub === t.key ? "active" : ""} onClick={() => setSub(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {sub === "estimate" ? (
        <StartupValuation entityId={entityId} onSaved={load} />
      ) : (
        <>
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

          {hasChart && (
            <div className="card">
              <h3>FMV over time</h3>
              <LineChart series={[fmvSeries, estSeries].filter((s) => s.points.length > 0)} />
            </div>
          )}

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
              <EmptyState icon="📈" title="No valuations yet" hint="Record an FMV (Rule 11UA / FEMA / fair value) to price ESOP grants, exercises and new rounds." />
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
        </>
      )}
    </div>
  );
}

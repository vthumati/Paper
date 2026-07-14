import { useEffect, useState } from "react";
import { api, type Runway } from "../api";
import Stat from "../components/Stat";

export default function Finance({ entityId }: { entityId: string }) {
  const [r, setR] = useState<Runway | null>(null);
  const [error, setError] = useState("");

  const [period, setPeriod] = useState("2026-06-01");
  const [cash, setCash] = useState("");
  const [burn, setBurn] = useState("");
  const [rev, setRev] = useState("");

  const load = () => api.runway(entityId).then(setR).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, [entityId]);

  async function add() {
    setError("");
    try {
      await api.addSnapshot(entityId, {
        period,
        cash_balance: cash || "0",
        monthly_burn: burn || "0",
        revenue: rev || "0",
      });
      setCash(""); setBurn(""); setRev("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h2>Runway</h2>
        {r && r.runway_months != null ? (
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Runway (months)" value={r.runway_months} big alert={r.runway_months < 6} />
            <Stat label="Cash (₹)" value={r.latest_cash ?? "—"} />
            <Stat label="Avg monthly burn (₹)" value={r.avg_monthly_burn ?? "—"} />
          </div>
        ) : (
          <p className="muted">Add a monthly snapshot (cash + burn) to compute runway.</p>
        )}
      </div>

      <div className="card">
        <h3>Add monthly snapshot</h3>
        <div className="row">
          <div><label>Month</label><input type="date" value={period} onChange={(e) => setPeriod(e.target.value)} /></div>
          <div><label>Cash balance (₹)</label><input value={cash} onChange={(e) => setCash(e.target.value)} /></div>
          <div><label>Monthly burn (₹)</label><input value={burn} onChange={(e) => setBurn(e.target.value)} /></div>
          <div><label>Revenue (₹)</label><input value={rev} onChange={(e) => setRev(e.target.value)} /></div>
        </div>
        <div style={{ marginTop: 10 }}>
          <button disabled={!cash} onClick={add}>Save snapshot</button>
        </div>
      </div>

      {r && r.snapshots.length > 0 && (
        <div className="card">
          <h3>History</h3>
          <table>
            <thead><tr><th>Month</th><th>Cash (₹)</th><th>Burn (₹)</th><th>Revenue (₹)</th></tr></thead>
            <tbody>
              {r.snapshots.map((s, i) => (
                <tr key={i}>
                  <td>{s.period}</td>
                  <td>{s.cash_balance}</td>
                  <td>{s.monthly_burn}</td>
                  <td>{s.revenue}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}


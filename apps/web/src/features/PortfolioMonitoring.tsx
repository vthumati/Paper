import { useEffect, useState } from "react";
import { api, type PortfolioMonitoring as Monitoring } from "../api";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";
import EmptyState from "../components/EmptyState";
import LineChart from "../components/LineChart";
import Stat from "../components/Stat";

const todayIso = () => new Date().toISOString().slice(0, 10);

/** Portfolio-company monitoring (Carta "portfolio monitoring"): collect operating
 * KPIs (revenue, cash, burn, headcount) per period per company, and roll them up
 * into a health dashboard — period-over-period revenue growth, runway, and a
 * low-runway flag. */
export default function PortfolioMonitoring({ fundId }: { fundId: string }) {
  const [mon, setMon] = useState<Monitoring | null>(null);
  const [open, setOpen] = useState(false);
  const [trend, setTrend] = useState<string | null>(null);
  const { error, guard } = useGuard(() => load());

  // report form
  const [invId, setInvId] = useState("");
  const [period, setPeriod] = useState("");
  const [asOf, setAsOf] = useState(todayIso());
  const [revenue, setRevenue] = useState("");
  const [cash, setCash] = useState("");
  const [burn, setBurn] = useState("");
  const [headcount, setHeadcount] = useState("");

  const load = () => api.portfolioMonitoring(fundId).then(setMon);
  useEffect(() => {
    load();
  }, [fundId]);

  if (!mon) return null;
  const t = mon.totals;

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>📈</span> Portfolio monitoring
        <button
          className="secondary"
          style={{ marginLeft: "auto" }}
          disabled={mon.companies.length === 0}
          onClick={() => {
            setOpen((v) => !v);
            if (!invId && mon.companies[0]) setInvId(mon.companies[0].investment_id);
          }}
        >
          {open ? "Close" : "Report KPIs"}
        </button>
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Track each portfolio company's operating KPIs over time. Runway = cash ÷ monthly burn;
        companies under 6 months are flagged.
      </p>
      {error && <p className="error">{error}</p>}

      {mon.companies.length === 0 ? (
        <EmptyState icon="📈" title="No portfolio companies yet" hint="Add investments above, then report their KPIs here to monitor revenue, burn and runway." />
      ) : (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            <Stat label="Companies reporting" value={`${t.reporting} / ${t.companies}`} />
            <Stat label="Latest revenue (sum)" value={fmtMoney(t.latest_revenue)} />
            <Stat label="Cash on hand (sum)" value={fmtMoney(t.cash)} />
            <Stat label="Low on runway" value={t.low_runway} alert={t.low_runway > 0} hint="Companies with under 6 months of runway" />
          </div>

          {open && (
            <div className="row" style={{ alignItems: "flex-end", marginTop: 12 }}>
              <div>
                <label>Company</label>
                <select value={invId} onChange={(e) => setInvId(e.target.value)}>
                  {mon.companies.map((c) => (
                    <option key={c.investment_id} value={c.investment_id}>{c.company_name}</option>
                  ))}
                </select>
              </div>
              <div><label>Period</label><input placeholder="FY26 Q2" value={period} onChange={(e) => setPeriod(e.target.value)} /></div>
              <div><label>As of</label><input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></div>
              <div><label>Revenue (₹)</label><input value={revenue} onChange={(e) => setRevenue(e.target.value)} /></div>
              <div><label>Cash (₹)</label><input value={cash} onChange={(e) => setCash(e.target.value)} /></div>
              <div><label>Monthly burn (₹)</label><input value={burn} onChange={(e) => setBurn(e.target.value)} /></div>
              <div><label>Headcount</label><input value={headcount} onChange={(e) => setHeadcount(e.target.value)} /></div>
              <button
                style={{ flex: "0 0 auto" }}
                disabled={!invId || !period}
                onClick={guard(async () => {
                  await api.addPortfolioKpi(fundId, invId, {
                    period_label: period,
                    as_of: asOf,
                    revenue: revenue || null,
                    cash: cash || null,
                    monthly_burn: burn || null,
                    headcount: headcount ? Number(headcount) : null,
                  });
                  setPeriod(""); setRevenue(""); setCash(""); setBurn(""); setHeadcount("");
                }, "KPIs reported")}
              >
                Save period
              </button>
            </div>
          )}

          <table style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Company</th><th>Revenue</th><th>Growth</th><th>Monthly burn</th>
                <th>Runway</th><th>Headcount</th><th>Latest period</th><th></th>
              </tr>
            </thead>
            <tbody>
              {mon.companies.map((c) => (
                <tr key={c.investment_id}>
                  <td>{c.company_name}</td>
                  <td>{c.latest?.revenue ? fmtMoney(c.latest.revenue) : <span className="muted">—</span>}</td>
                  <td>
                    {c.revenue_growth_pct === null ? (
                      <span className="muted">—</span>
                    ) : (
                      <span className={c.revenue_growth_pct >= 0 ? "delta-up" : "delta-down"}>
                        {c.revenue_growth_pct >= 0 ? "▲" : "▼"} {Math.abs(c.revenue_growth_pct)}%
                      </span>
                    )}
                  </td>
                  <td>{c.latest?.monthly_burn ? fmtMoney(c.latest.monthly_burn) : <span className="muted">—</span>}</td>
                  <td>
                    {c.runway_months === null ? (
                      <span className="muted">—</span>
                    ) : (
                      <span className={`badge ${c.low_runway ? "danger" : "complete"}`}>
                        {c.runway_months} mo
                      </span>
                    )}
                  </td>
                  <td>{c.latest?.headcount ?? <span className="muted">—</span>}</td>
                  <td>{c.latest ? <span className="muted">{c.latest.period_label}</span> : <span className="muted">no data</span>}</td>
                  <td>
                    {c.revenue_series.length > 1 && (
                      <button
                        className="secondary"
                        onClick={() => setTrend(trend === c.investment_id ? null : c.investment_id)}
                      >
                        {trend === c.investment_id ? "Hide" : "Trend"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {trend && (() => {
            const c = mon.companies.find((x) => x.investment_id === trend);
            if (!c) return null;
            return (
              <div style={{ marginTop: 12 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                  {c.company_name} — revenue trend
                </div>
                <LineChart series={[{ label: "Revenue", color: "var(--blue)", points: c.revenue_series }]} height={180} />
              </div>
            );
          })()}
        </>
      )}
    </div>
  );
}

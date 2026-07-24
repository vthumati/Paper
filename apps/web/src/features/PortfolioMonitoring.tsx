import { useEffect, useState } from "react";
import {
  api,
  type KPIDefinitionList,
  type KPIRequest,
  type KPISchedule,
  type MetricAlertRuleList,
  type PortfolioBenchmarks,
  type PortfolioMonitoring as Monitoring,
  type PortfolioSignals,
} from "../api";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";
import Avatar from "../components/Avatar";
import { CHART_COLORS } from "../components/Donut";
import EmptyState from "../components/EmptyState";
import LineChart from "../components/LineChart";
import PageHeader from "../components/PageHeader";
import Sparkline from "../components/Sparkline";
import Stat from "../components/Stat";

const todayIso = () => new Date().toISOString().slice(0, 10);

const fmtMetric = (v: number | null | undefined, unit: string) =>
  v === null || v === undefined ? null : unit === "inr" ? fmtMoney(v) : unit === "pct" ? `${v}%` : String(v);

// Vestberry-style 0-10 risk score derived from the signals panel's severities
const SEVERITY_WEIGHT: Record<string, number> = { high: 3, warn: 2, info: 1 };
const riskScore = (signals: PortfolioSignals | null, invId: string) => {
  const c = signals?.companies.find((x) => x.investment_id === invId);
  if (!c) return 0;
  return Math.min(10, c.signals.reduce((s, x) => s + (SEVERITY_WEIGHT[x.severity] ?? 0), 0));
};

const STALE_DAYS = 183;
const isStale = (asOf: string) =>
  (Date.now() - new Date(asOf).getTime()) / 86400000 > STALE_DAYS;

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

  // KPI requests (investee self-service)
  const [reqs, setReqs] = useState<KPIRequest[]>([]);
  const [schedules, setSchedules] = useState<KPISchedule[]>([]);
  const [cadence, setCadence] = useState<"monthly" | "quarterly">("quarterly");
  const [reqOpen, setReqOpen] = useState(false);
  const [rInvId, setRInvId] = useState("");
  const [rPeriod, setRPeriod] = useState("");
  const [rAsOf, setRAsOf] = useState(todayIso());
  const [rDue, setRDue] = useState("");
  const [rEmail, setREmail] = useState("");

  // custom KPI definitions + benchmarking
  const [defs, setDefs] = useState<KPIDefinitionList | null>(null);
  const [defsOpen, setDefsOpen] = useState(false);
  const [defLabel, setDefLabel] = useState("");
  const [defUnit, setDefUnit] = useState("number");
  const [custom, setCustom] = useState<Record<string, string>>({});
  const [bench, setBench] = useState<PortfolioBenchmarks | null>(null);
  const [signals, setSignals] = useState<PortfolioSignals | null>(null);

  // metric alert rules (Visible-style thresholds)
  const [alerts, setAlerts] = useState<MetricAlertRuleList | null>(null);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [aMetric, setAMetric] = useState("revenue");
  const [aComp, setAComp] = useState<"lt" | "gt">("lt");
  const [aThreshold, setAThreshold] = useState("");
  const [aSeverity, setASeverity] = useState<"high" | "warn">("warn");
  const [aBasis, setABasis] = useState<"value" | "pct_change">("value");

  const load = () =>
    Promise.all([
      api.portfolioMonitoring(fundId).then(setMon),
      api.listKpiRequests(fundId).then(setReqs),
      api.listKpiDefinitions(fundId).then(setDefs),
      api.portfolioBenchmarks(fundId).then(setBench),
      api.portfolioSignals(fundId).then(setSignals),
      api.listAlertRules(fundId).then(setAlerts),
      api.listKpiSchedules(fundId).then(setSchedules),
    ]);
  useEffect(() => {
    load();
  }, [fundId]);

  if (!mon) return null;
  const t = mon.totals;

  return (
    <div className="card">
      <PageHeader
        icon="📈"
        title="Portfolio monitoring"
        subtitle="Operating KPIs, runway and health across the portfolio"
        right={
          <>
            <button
              className="secondary"
              onClick={() => setDefsOpen((v) => !v)}
              title="Define the fund's own metrics (incl. ESG presets) to collect alongside the core KPIs"
            >
              {defsOpen ? "Close metrics" : "Custom metrics"}
            </button>
            <button
              className="secondary"
              onClick={() => setAlertsOpen((v) => !v)}
              title="Set performance thresholds on tracked metrics — breaches surface as portfolio signals"
            >
              {alertsOpen ? "Close alerts" : "Metric alerts"}
            </button>
            <button
              className="secondary"
              disabled={mon.companies.length === 0}
              title="Download every company's KPI history as CSV"
              onClick={guard(() => api.exportKpisCsv(fundId))}
            >
              Export KPIs
            </button>
            <button
              className="secondary"
              disabled={mon.companies.length === 0}
              onClick={() => {
                setReqOpen((v) => !v);
                if (!rInvId && mon.companies[0]) setRInvId(mon.companies[0].investment_id);
              }}
              title="Ask the company's reporting contact to submit KPIs from their portal"
            >
              {reqOpen ? "Close request" : "Request KPIs"}
            </button>
            <button
              className="secondary"
              disabled={mon.companies.length === 0}
              onClick={() => {
                setOpen((v) => !v);
                if (!invId && mon.companies[0]) setInvId(mon.companies[0].investment_id);
              }}
            >
              {open ? "Close" : "Report KPIs"}
            </button>
          </>
        }
      />
      <p className="muted" style={{ marginTop: 0 }}>
        Track each portfolio company's operating KPIs over time. Runway = cash ÷ monthly burn;
        companies under 6 months are flagged.
      </p>
      {error && <p className="error">{error}</p>}

      {defsOpen && defs && (
        <div style={{ margin: "10px 0" }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            Custom metrics collected with each KPI period — define your own or add an ESG preset.
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
            {defs.definitions.length === 0 && <span className="muted">No custom metrics defined yet.</span>}
            {defs.definitions.map((d) => (
              <span key={d.id} className="badge">
                {d.label} <span className="muted">({d.unit})</span>{" "}
                <a
                  href="#"
                  title="Remove this metric (historical values are kept)"
                  onClick={(e) => {
                    e.preventDefault();
                    guard(async () => {
                      await api.deleteKpiDefinition(fundId, d.id);
                    }, "Metric removed")();
                  }}
                >
                  ×
                </a>
              </span>
            ))}
          </div>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <div><label>New metric</label><input placeholder="GMV (monthly)" value={defLabel} onChange={(e) => setDefLabel(e.target.value)} /></div>
            <div>
              <label>Unit</label>
              <select value={defUnit} onChange={(e) => setDefUnit(e.target.value)}>
                <option value="inr">₹ amount</option>
                <option value="number">number</option>
                <option value="pct">%</option>
              </select>
            </div>
            <button
              style={{ flex: "0 0 auto" }}
              disabled={!defLabel.trim()}
              onClick={guard(async () => {
                await api.addKpiDefinition(fundId, { label: defLabel, unit: defUnit });
                setDefLabel("");
              }, "Metric defined")}
            >
              Add metric
            </button>
          </div>
          {defs.presets.some((p) => !defs.definitions.find((d) => d.key === p.key)) && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, alignItems: "center" }}>
              <span className="muted" style={{ fontSize: 12 }}>ESG presets:</span>
              {defs.presets
                .filter((p) => !defs.definitions.find((d) => d.key === p.key))
                .map((p) => (
                  <button
                    key={p.key}
                    className="secondary"
                    onClick={guard(async () => {
                      await api.addKpiDefinition(fundId, p);
                    }, "ESG metric added")}
                  >
                    + {p.label}
                  </button>
                ))}
            </div>
          )}
        </div>
      )}

      {alertsOpen && alerts && (
        <div style={{ margin: "10px 0" }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            Alert when a company's latest reported value crosses a threshold, or when a metric
            changes more than a % vs the prior period (e.g. burn rises &gt;20%) — breaches appear in
            the signals panel with the chosen severity.
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
            {alerts.rules.length === 0 && <span className="muted">No alert rules yet.</span>}
            {alerts.rules.map((r) => {
              const m = alerts.metrics.find((x) => x.key === r.metric);
              return (
                <span key={r.id} className={`badge ${r.severity === "high" ? "danger" : ""}`}>
                  {m?.label ?? r.metric}{r.basis === "pct_change" ? " Δ" : ""}{" "}
                  {r.comparator === "lt" ? "<" : ">"}{" "}
                  {r.basis === "pct_change"
                    ? `${r.threshold}%`
                    : fmtMetric(Number(r.threshold), m?.unit ?? "number")}{" "}
                  <a
                    href="#"
                    title="Remove this alert rule"
                    onClick={(e) => {
                      e.preventDefault();
                      guard(async () => {
                        await api.deleteAlertRule(fundId, r.id);
                      }, "Alert rule removed")();
                    }}
                  >
                    ×
                  </a>
                </span>
              );
            })}
          </div>
          <div className="row" style={{ alignItems: "flex-end" }}>
            <div>
              <label>Metric</label>
              <select value={aMetric} onChange={(e) => setAMetric(e.target.value)}>
                {alerts.metrics.map((m) => (
                  <option key={m.key} value={m.key}>{m.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label>Basis</label>
              <select value={aBasis} onChange={(e) => setABasis(e.target.value as "value" | "pct_change")}>
                <option value="value">latest value</option>
                <option value="pct_change">% change vs prior</option>
              </select>
            </div>
            <div>
              <label>Condition</label>
              <select value={aComp} onChange={(e) => setAComp(e.target.value as "lt" | "gt")}>
                <option value="lt">falls below</option>
                <option value="gt">rises above</option>
              </select>
            </div>
            <div>
              <label>{aBasis === "pct_change" ? "% change" : "Threshold"}</label>
              <input placeholder={aBasis === "pct_change" ? "e.g. 20" : "e.g. 6"} value={aThreshold} onChange={(e) => setAThreshold(e.target.value)} />
            </div>
            <div>
              <label>Severity</label>
              <select value={aSeverity} onChange={(e) => setASeverity(e.target.value as "high" | "warn")}>
                <option value="warn">warning</option>
                <option value="high">high</option>
              </select>
            </div>
            <button
              style={{ flex: "0 0 auto" }}
              disabled={!aThreshold.trim() || isNaN(Number(aThreshold))}
              onClick={guard(async () => {
                await api.addAlertRule(fundId, {
                  metric: aMetric, comparator: aComp, threshold: aThreshold,
                  severity: aSeverity, basis: aBasis,
                });
                setAThreshold("");
              }, "Alert rule added")}
            >
              Add alert
            </button>
          </div>
        </div>
      )}

      {mon.companies.length === 0 ? (
        <EmptyState icon="📈" title="No portfolio companies yet" hint="Add investments above, then report their KPIs here to monitor revenue, burn and runway." />
      ) : (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
            <Stat label="Companies reporting" value={`${t.reporting} / ${t.companies}`} />
            <Stat
              label="Latest revenue (sum)"
              value={fmtMoney(t.latest_revenue)}
              deltas={(() => {
                const last = (xs: { y: number }[], back: number) => xs[xs.length - back]?.y;
                const now = mon.companies.reduce((s, c) => s + (last(c.revenue_series, 1) ?? 0), 0);
                const prev = mon.companies.reduce(
                  (s, c) => s + (last(c.revenue_series, 2) ?? last(c.revenue_series, 1) ?? 0),
                  0
                );
                if (!prev || prev === now) return undefined;
                return [{ label: "vs prior period", pct: Math.round(((now - prev) / prev) * 1000) / 10 }];
              })()}
            />
            <Stat label="Cash on hand (sum)" value={fmtMoney(t.cash)} />
            <Stat label="Low on runway" value={t.low_runway} alert={t.low_runway > 0} hint="Companies with under 6 months of runway" />
          </div>

          <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10, alignItems: "center" }}>
            <span className="muted" style={{ fontSize: 12 }}>Reporting status:</span>
            {mon.companies.map((c) => {
              const req = reqs.find(
                (r) => r.investment_id === c.investment_id && r.status !== "accepted"
              );
              const chip = req?.overdue
                ? { cls: "danger", text: `overdue (${req.period_label})` }
                : req
                ? { cls: "active", text: req.status === "submitted" ? `submitted (${req.period_label})` : `requested (${req.period_label})` }
                : c.latest
                ? { cls: "complete", text: `✓ ${c.latest.period_label}` }
                : { cls: "", text: "never reported" };
              return (
                <span key={c.investment_id} className={`badge ${chip.cls}`} title={c.latest ? `Latest period as of ${c.latest.as_of}` : "No KPI periods yet"}>
                  {c.company_name} · {chip.text}
                </span>
              );
            })}
          </div>

          {reqOpen && (
            <div className="row" style={{ alignItems: "flex-end", marginTop: 12 }}>
              <div>
                <label>Company</label>
                <select
                  value={rInvId}
                  onChange={(e) => {
                    setRInvId(e.target.value);
                    const c = mon.companies.find((x) => x.investment_id === e.target.value);
                    if (c?.contact_email) setREmail(c.contact_email);
                  }}
                >
                  {mon.companies.map((c) => (
                    <option key={c.investment_id} value={c.investment_id}>{c.company_name}</option>
                  ))}
                </select>
              </div>
              <div><label>Period</label><input placeholder="FY27 Q1" value={rPeriod} onChange={(e) => setRPeriod(e.target.value)} /></div>
              <div><label>Period end</label><input type="date" value={rAsOf} onChange={(e) => setRAsOf(e.target.value)} /></div>
              <div><label>Due date</label><input type="date" value={rDue} onChange={(e) => setRDue(e.target.value)} /></div>
              <div><label>Contact email</label><input placeholder="founder@company.in" value={rEmail} onChange={(e) => setREmail(e.target.value)} /></div>
              <button
                style={{ flex: "0 0 auto" }}
                disabled={!rInvId || !rPeriod || !rEmail}
                onClick={guard(async () => {
                  const r = await api.createKpiRequest(fundId, rInvId, {
                    period_label: rPeriod,
                    as_of: rAsOf,
                    due_date: rDue || null,
                    contact_email: rEmail,
                  });
                  setReqs(r);
                  setRPeriod("");
                }, "KPI request sent — the contact will see it in their portal")}
              >
                Send request
              </button>
              <div style={{ flex: "0 0 auto" }}>
                <label>Or recurring</label>
                <select value={cadence} onChange={(e) => setCadence(e.target.value as "monthly" | "quarterly")}>
                  <option value="quarterly">every quarter</option>
                  <option value="monthly">every month</option>
                </select>
              </div>
              <button
                className="secondary"
                style={{ flex: "0 0 auto" }}
                disabled={!rInvId || !rEmail}
                title="Auto-create the request for each completed period — no need to remember the cadence"
                onClick={guard(async () => {
                  await api.upsertKpiSchedule(fundId, rInvId, { cadence, contact_email: rEmail });
                }, "Recurring schedule set — requests appear as each period completes")}
              >
                Make recurring
              </button>
            </div>
          )}

          {reqOpen && schedules.length > 0 && (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, alignItems: "center" }}>
              <span className="muted" style={{ fontSize: 12 }}>Recurring:</span>
              {schedules.map((s) => (
                <span key={s.id} className="badge">
                  {s.company_name} · {s.cadence}{" "}
                  <a
                    href="#"
                    title="Stop the recurring schedule (existing requests stay)"
                    onClick={(e) => {
                      e.preventDefault();
                      guard(async () => {
                        await api.deleteKpiSchedule(fundId, s.investment_id);
                      }, "Schedule removed")();
                    }}
                  >
                    ×
                  </a>
                </span>
              ))}
            </div>
          )}

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
              {(defs?.definitions ?? []).map((d) => (
                <div key={d.key}>
                  <label>{d.label}{d.unit === "inr" ? " (₹)" : d.unit === "pct" ? " (%)" : ""}</label>
                  <input
                    value={custom[d.key] ?? ""}
                    onChange={(e) => setCustom({ ...custom, [d.key]: e.target.value })}
                  />
                </div>
              ))}
              <button
                style={{ flex: "0 0 auto" }}
                disabled={!invId || !period}
                onClick={guard(async () => {
                  const customVals = Object.fromEntries(
                    Object.entries(custom).filter(([, v]) => v !== "")
                  );
                  await api.addPortfolioKpi(fundId, invId, {
                    period_label: period,
                    as_of: asOf,
                    revenue: revenue || null,
                    cash: cash || null,
                    monthly_burn: burn || null,
                    headcount: headcount ? Number(headcount) : null,
                    custom: Object.keys(customVals).length ? customVals : undefined,
                  });
                  setPeriod(""); setRevenue(""); setCash(""); setBurn(""); setHeadcount(""); setCustom({});
                }, "KPIs reported")}
              >
                Save period
              </button>
            </div>
          )}

          {reqs.length > 0 && (
            <>
              <div className="muted" style={{ fontSize: 12, margin: "14px 0 4px" }}>
                KPI requests — companies report from their own portal; accept to add the period
              </div>
              <table>
                <thead>
                  <tr><th>Company</th><th>Period</th><th>Due</th><th>Contact</th><th>Status</th><th>Submitted</th><th></th></tr>
                </thead>
                <tbody>
                  {reqs.map((r) => (
                    <tr key={r.id}>
                      <td>{r.company_name}</td>
                      <td>{r.period_label}</td>
                      <td>{r.due_date ?? <span className="muted">—</span>}</td>
                      <td className="muted">{r.contact_email}</td>
                      <td>
                        {r.status === "accepted" ? (
                          <span className="badge complete">accepted</span>
                        ) : r.status === "submitted" ? (
                          <span className="badge active">submitted</span>
                        ) : r.overdue ? (
                          <span className="badge danger">overdue</span>
                        ) : (
                          <span className="badge">pending</span>
                        )}
                      </td>
                      <td className="muted" style={{ fontSize: 12 }}>
                        {r.status === "submitted" || r.status === "accepted" ? (
                          <>
                            rev {r.revenue ? fmtMoney(r.revenue) : "—"} · cash {r.cash ? fmtMoney(r.cash) : "—"} ·
                            burn {r.monthly_burn ? fmtMoney(r.monthly_burn) : "—"} · HC {r.headcount ?? "—"}
                          </>
                        ) : (
                          "—"
                        )}
                      </td>
                      <td>
                        {r.status === "submitted" && (
                          <>
                            <button
                              className="secondary"
                              onClick={guard(async () => setReqs(await api.acceptKpiRequest(fundId, r.id)), "KPIs accepted into monitoring")}
                            >
                              Accept
                            </button>{" "}
                            <button
                              className="secondary"
                              title="Send back for resubmission"
                              onClick={guard(async () => setReqs(await api.reopenKpiRequest(fundId, r.id)), "Request reopened")}
                            >
                              Reopen
                            </button>
                          </>
                        )}
                        {r.status === "pending" && r.token && (
                          <button
                            className="secondary"
                            title="Copy a no-login submission link — the contact can report without a Paper account"
                            onClick={guard(async () => {
                              const link = `${window.location.origin}/submit-kpis/${r.token}`;
                              try {
                                await navigator.clipboard.writeText(link);
                              } catch {
                                window.prompt("Copy the submission link:", link);
                              }
                            }, "Submission link copied")}
                          >
                            Copy link
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          <table style={{ marginTop: 12 }}>
            <thead>
              <tr>
                <th>Company</th><th>Risk</th><th>Revenue</th><th>Growth</th><th>Monthly burn</th>
                <th>Runway</th><th>Headcount</th><th>Latest period</th><th></th>
              </tr>
            </thead>
            <tbody>
              {mon.companies.map((c) => (
                <tr key={c.investment_id}>
                  <td>
                    <Avatar name={c.company_name} /> {c.company_name}
                    {c.sector && <> <span className="badge">{c.sector}</span></>}
                  </td>
                  <td>
                    {(() => {
                      const score = riskScore(signals, c.investment_id);
                      return (
                        <span
                          className={`badge ${score >= 6 ? "danger" : score >= 3 ? "active" : "complete"}`}
                          title="Severity-weighted signal score (0 = all clear, 10 = worst) — see the Signals panel"
                        >
                          {score}
                        </span>
                      );
                    })()}
                  </td>
                  <td>
                    {c.latest?.revenue ? fmtMoney(c.latest.revenue) : <span className="muted">—</span>}
                    {c.revenue_series.length > 1 && (
                      <Sparkline
                        points={c.revenue_series.map((p) => p.y)}
                        color={(c.revenue_growth_pct ?? 0) >= 0 ? "var(--ok, #0f9d6b)" : "#c0552f"}
                      />
                    )}
                  </td>
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
                  <td>
                    {c.latest ? (
                      isStale(c.latest.as_of) ? (
                        <span className="badge danger" title={`Last reported ${c.latest.as_of} — over 6 months ago`}>
                          {c.latest.period_label}
                        </span>
                      ) : (
                        <span className="muted">{c.latest.period_label}</span>
                      )
                    ) : (
                      <span className="muted">no data</span>
                    )}
                  </td>
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

          {(() => {
            // portfolio-wide revenue overlay — every company with 2+ periods as a series
            const overlay = mon.companies
              .filter((c) => c.revenue_series.length > 1)
              .map((c, i) => ({
                label: c.company_name,
                color: CHART_COLORS[i % CHART_COLORS.length],
                points: c.revenue_series,
              }));
            if (overlay.length < 2) return null;
            return (
              <div style={{ marginTop: 14 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                  Portfolio revenue — all companies
                </div>
                <LineChart series={overlay} height={200} />
              </div>
            );
          })()}

          {bench && bench.rows.length > 1 && Object.values(bench.medians).some((v) => v !== null) && (
            <>
              <div className="muted" style={{ fontSize: 12, margin: "14px 0 4px" }}>
                Internal benchmarking — each company's latest period vs the portfolio median
                (▲ above · ▼ below)
              </div>
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    {bench.metrics.map((m) => <th key={m.key}>{m.label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {([
                    ["TOTAL", (k: string, unit: string) => (unit === "inr" ? bench.stats[k]?.total ?? null : null)],
                    ["AVERAGE", (k: string) => bench.stats[k]?.avg ?? null],
                    ["MEDIAN", (k: string) => bench.stats[k]?.median ?? null],
                  ] as const).map(([label, pick]) => (
                    <tr key={label} style={{ background: "var(--light)" }}>
                      <td style={{ fontWeight: 700, color: "var(--heading)" }}>{label}</td>
                      {bench.metrics.map((m) => (
                        <td key={m.key} style={{ fontWeight: 600 }}>
                          {fmtMetric(pick(m.key, m.unit), m.unit) ?? <span className="muted">—</span>}
                        </td>
                      ))}
                    </tr>
                  ))}
                  {bench.rows.map((r) => (
                    <tr key={r.investment_id}>
                      <td>{r.company_name}</td>
                      {bench.metrics.map((m) => {
                        const v = r.values[m.key];
                        const med = bench.medians[m.key];
                        const txt = fmtMetric(v, m.unit);
                        return (
                          <td key={m.key}>
                            {txt === null ? (
                              <span className="muted">—</span>
                            ) : v !== null && med !== null && v !== med ? (
                              <span className={v > med ? "delta-up" : "delta-down"}>
                                {v > med ? "▲" : "▼"} {txt}
                              </span>
                            ) : (
                              txt
                            )}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>

              {bench.segments.length > 0 && (
                <>
                  <div className="muted" style={{ fontSize: 12, margin: "14px 0 4px" }}>
                    Segment comparison — medians per sector cohort
                  </div>
                  <table>
                    <thead>
                      <tr>
                        <th>Segment</th>
                        <th>Companies</th>
                        {bench.metrics.map((m) => <th key={m.key}>{m.label}</th>)}
                      </tr>
                    </thead>
                    <tbody>
                      {bench.segments.map((s) => (
                        <tr key={s.segment}>
                          <td><span className="badge">{s.segment}</span></td>
                          <td>{s.companies}</td>
                          {bench.metrics.map((m) => (
                            <td key={m.key}>{fmtMetric(s.medians[m.key], m.unit) ?? <span className="muted">—</span>}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              <div style={{ marginTop: 12, display: "grid", gap: 7 }}>
                {bench.metrics.map((m) => {
                  const vals = bench.rows
                    .map((r) => ({ name: r.company_name, v: r.values[m.key] }))
                    .filter((x): x is { name: string; v: number } => x.v !== null);
                  if (vals.length < 2) return null;
                  const min = Math.min(...vals.map((x) => x.v));
                  const max = Math.max(...vals.map((x) => x.v));
                  const span = max - min || 1;
                  const med = bench.medians[m.key];
                  return (
                    <div key={m.key} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span className="muted" style={{ fontSize: 12, flex: "0 0 160px" }}>{m.label}</span>
                      <div style={{ position: "relative", flex: 1, height: 14, background: "rgba(120,120,120,0.12)", borderRadius: 7 }}>
                        {(() => {
                          const st = bench.stats[m.key];
                          if (!st || st.reporters < 2) return null;
                          return [["Q1", st.q1] as const, ["Q3", st.q3] as const].map(([lbl, q]) => (
                            <span
                              key={lbl}
                              title={`${lbl} ${fmtMetric(q, m.unit)}`}
                              style={{ position: "absolute", left: `${((q - min) / span) * 100}%`, top: 1, bottom: 1, width: 0, borderLeft: "2px dotted var(--muted)", opacity: 0.7 }}
                            />
                          ));
                        })()}
                        {med !== null && (
                          <span
                            title={`Median ${fmtMetric(med, m.unit)}`}
                            style={{ position: "absolute", left: `${((med - min) / span) * 100}%`, top: -2, bottom: -2, width: 2, background: "var(--heading)", opacity: 0.55 }}
                          />
                        )}
                        {vals.map((x) => (
                          <span
                            key={x.name}
                            title={`${x.name}: ${fmtMetric(x.v, m.unit)}`}
                            style={{ position: "absolute", left: `calc(${((x.v - min) / span) * 100}% - 5px)`, top: 2, width: 10, height: 10, borderRadius: "50%", background: "var(--blue)", opacity: 0.85 }}
                          />
                        ))}
                      </div>
                      <span className="muted" style={{ fontSize: 11, flex: "0 0 190px", textAlign: "right" }}>
                        {fmtMetric(min, m.unit)} – {fmtMetric(max, m.unit)}
                      </span>
                    </div>
                  );
                })}
              </div>

              {bench.metrics.some((m) => (bench.stats[m.key]?.reporters ?? 0) >= 2) && (
                <>
                  <div className="muted" style={{ fontSize: 12, margin: "14px 0 4px" }}>
                    Distribution — quartiles across reporting companies (dotted Q1/Q3 marks on the strips above)
                  </div>
                  <table>
                    <thead>
                      <tr><th>Metric</th><th>Reporters</th><th>Min</th><th>Q1</th><th>Median</th><th>Q3</th><th>Max</th><th>Total</th></tr>
                    </thead>
                    <tbody>
                      {bench.metrics.map((m) => {
                        const st = bench.stats[m.key];
                        if (!st || st.reporters < 2) return null;
                        return (
                          <tr key={m.key}>
                            <td>{m.label}</td>
                            <td>{st.reporters}</td>
                            <td>{fmtMetric(st.min, m.unit)}</td>
                            <td>{fmtMetric(st.q1, m.unit)}</td>
                            <td><strong>{fmtMetric(st.median, m.unit)}</strong></td>
                            <td>{fmtMetric(st.q3, m.unit)}</td>
                            <td>{fmtMetric(st.max, m.unit)}</td>
                            <td className="muted">{m.unit === "inr" ? fmtMetric(st.total, m.unit) : "—"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

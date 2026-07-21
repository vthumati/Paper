import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { uiPrompt } from "../components/Prompt";
import ColumnChart from "../components/ColumnChart";
import LpReportView from "../components/LpReportView";
import Stat from "../components/Stat";
import DealPipeline from "./DealPipeline";
import FundForecast from "./FundForecast";
import FundDDQ from "./FundDDQ";
import FundNetwork from "./FundNetwork";
import FundRaise from "./FundRaise";
import TearSheet from "./TearSheet";
import FundSignals from "./FundSignals";
import FundFinancials from "./FundFinancials";
import FundValuations from "./FundValuations";
import PortfolioMonitoring from "./PortfolioMonitoring";
import { useGuard } from "../hooks";
import { fmtInt, fmtMoney } from "../lib/format";
import {
  api,
  ApiError,
  type CapitalAccounts,
  type CapitalCall,
  type Distribution,
  type Fund as FundT,
  type FundPerformance,
  type LP,
  type LpReportData,
  type PerformancePoint,
  type PortfolioInvestment,
  type ScheduleOfInvestments,
} from "../api";

// Fund workspace sub-tabs (CapTableHub pattern) — the header summary card
// stays visible above them.
const SUBTABS = [
  { key: "capital", label: "Capital & LPs" },
  { key: "fundraise", label: "LP fundraise" },
  { key: "portfolio", label: "Portfolio" },
  { key: "deals", label: "Deal pipeline" },
  { key: "plan", label: "Plan & forecast" },
  { key: "reports", label: "Financials" },
] as const;
type SubTab = (typeof SUBTABS)[number]["key"];

export default function Fund({
  entityId,
  initialSub,
}: {
  entityId: string;
  /** ?tab=fund&sub=<key> deep link (command palette, shared URLs) */
  initialSub?: string | null;
}) {
  const [fund, setFund] = useState<FundT | null>(null);
  const [sub, setSub] = useState<SubTab>(
    initialSub && SUBTABS.some((t) => t.key === initialSub)
      ? (initialSub as SubTab)
      : "capital"
  );
  useEffect(() => {
    if (initialSub && SUBTABS.some((t) => t.key === initialSub)) {
      setSub(initialSub as SubTab);
    }
  }, [initialSub]);
  const [lps, setLps] = useState<LP[]>([]);
  const [calls, setCalls] = useState<CapitalCall[]>([]);
  const [dists, setDists] = useState<Distribution[]>([]);
  const [accounts, setAccounts] = useState<CapitalAccounts | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioInvestment[]>([]);
  const [soi, setSoi] = useState<ScheduleOfInvestments | null>(null);
  const [perf, setPerf] = useState<FundPerformance | null>(null);
  const [series, setSeries] = useState<PerformancePoint[]>([]);
  const [note, setNote] = useState("");
  const { error, setError, guard } = useGuard(async () => {
    if (fund) await refresh(fund.id);
  });

  // forms
  const [cat, setCat] = useState("II");
  const [lpName, setLpName] = useState("");
  const [lpCommit, setLpCommit] = useState("");
  const [callPct, setCallPct] = useState("25");
  const [distAmt, setDistAmt] = useState("");
  const [distKind, setDistKind] = useState("profit");
  const [coName, setCoName] = useState("");
  const [coAmt, setCoAmt] = useState("");
  const [coSector, setCoSector] = useState("");
  const [openTear, setOpenTear] = useState<string | null>(null);
  const [reportView, setReportView] = useState<LpReportData | null>(null);

  async function loadFund() {
    try {
      const f = await api.getFund(entityId);
      setFund(f);
      await refresh(f.id);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setFund(null);
      else setError((e as Error).message);
    }
  }
  async function refresh(fid: string) {
    const [l, c, d, a, p, pf, s, ps] = await Promise.all([
      api.listLPs(fid),
      api.listCalls(fid),
      api.listDistributions(fid),
      api.capitalAccounts(fid),
      api.listPortfolio(fid),
      api.fundPerformance(fid),
      api.scheduleOfInvestments(fid),
      api.performanceSeries(fid),
    ]);
    setLps(l);
    setCalls(c);
    setDists(d);
    setAccounts(a);
    setPortfolio(p);
    setPerf(pf);
    setSoi(s);
    setSeries(ps);
  }
  useEffect(() => {
    loadFund();
  }, [entityId]);

  if (!fund) {
    return (
      <div className="card">
        {error && <p className="error">{error}</p>}
        <h2>Set up fund (AIF)</h2>
        <label>SEBI category</label>
        <select value={cat} onChange={(e) => setCat(e.target.value)} style={{ maxWidth: 200 }}>
          <option value="I">Category I</option>
          <option value="II">Category II</option>
          <option value="III">Category III</option>
        </select>
        <div style={{ marginTop: 10 }}>
          <button
            onClick={guard(async () => {
              await api.createFund(entityId, { sebi_category: cat });
              await loadFund();
            })}
          >
            Create fund
          </button>
        </div>
      </div>
    );
  }

  // Visible-style change pills: latest series value vs ~a quarter / ~a year ago
  const deltasFor = (key: "nav" | "tvpi" | "dpi" | "rvpi") => {
    if (series.length < 2) return undefined;
    const latest = Number(series[series.length - 1][key]);
    if (!isFinite(latest)) return undefined;
    const at = (days: number) => {
      const cutoff = Date.now() - days * 86400000;
      const past = [...series].reverse().find((p) => new Date(p.date).getTime() <= cutoff);
      return past ? Number(past[key]) : null;
    };
    const out: { label: string; pct: number }[] = [];
    for (const [label, days] of [["vs last quarter", 91], ["vs last year", 365]] as const) {
      const base = at(days);
      if (base !== null && base !== 0 && isFinite(base)) {
        const pct = Math.round(((latest - base) / Math.abs(base)) * 1000) / 10;
        if (pct !== 0) out.push({ label, pct });
      }
    }
    if (out.length === 0) {
      // young fund: no point a quarter back yet — show the move since inception
      const first = Number(series[0][key]);
      if (isFinite(first) && first !== 0 && first !== latest) {
        out.push({
          label: "since inception",
          pct: Math.round(((latest - first) / Math.abs(first)) * 1000) / 10,
        });
      }
    }
    return out.length ? out : undefined;
  };

  return (
    <div>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}
      <div className="card">
        <h2>
          Fund · SEBI Cat {fund.sebi_category}{" "}
          <span className="badge">carry {(Number(fund.carry_pct) * 100).toFixed(0)}%</span>{" "}
          <span className="badge">hurdle {(Number(fund.hurdle_pct) * 100).toFixed(0)}%</span>{" "}
          <span className="badge">fee {(Number(fund.mgmt_fee_pct) * 100).toFixed(1)}% on {fund.fee_basis}</span>
        </h2>
        {accounts && (
          <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 10 }}>
            <Stat label="Committed" value={fmtMoney(accounts.totals.committed)} />
            <Stat label="Drawn" value={fmtMoney(accounts.totals.drawn)} />
            <Stat label="Uncalled" value={fmtMoney(accounts.totals.remaining)} />
            <Stat label="Distributed" value={fmtMoney(accounts.totals.distributed)} />
            {perf && perf.paid_in !== "0.00" && (
              <>
                <Stat
                  label="NAV"
                  value={fmtMoney(perf.nav)}
                  spark={series.map((p) => Number(p.nav))}
                  deltas={deltasFor("nav")}
                  hint={
                    perf.positions_at_cost > 0
                      ? `${perf.positions_at_cost} position(s) held at cost — mark them under Portfolio`
                      : "Portfolio at the fund's marks"
                  }
                />
                <Stat label="TVPI" value={perf.tvpi ?? "—"} spark={series.map((p) => Number(p.tvpi))} deltas={deltasFor("tvpi")} hint="Total value to paid-in" />
                <Stat label="DPI" value={perf.dpi ?? "—"} spark={series.map((p) => Number(p.dpi))} deltas={deltasFor("dpi")} hint="Distributions to paid-in" />
                <Stat label="RVPI" value={perf.rvpi ?? "—"} spark={series.map((p) => Number(p.rvpi))} deltas={deltasFor("rvpi")} hint="Residual value to paid-in" />
                <Stat label="XIRR" value={perf.xirr_pct !== null ? `${perf.xirr_pct}%` : "—"} hint="Money-weighted annualised return" />
                {perf.nav_per_unit && (
                  <Stat
                    label="NAV / unit"
                    value={fmtMoney(perf.nav_per_unit)}
                    hint={`${fmtInt(perf.units_outstanding)} units outstanding at ₹10 par`}
                  />
                )}
              </>
            )}
          </div>
        )}
        {perf && Number(perf.management_fee_accrued) > 0 && (
          <p className="muted" style={{ margin: "8px 0 4px" }}>
            Management fee accrued {fmtMoney(perf.management_fee_accrued)}
          </p>
        )}
        {perf && Number(perf.management_fee_accrued) > 0 && (
          <button
            className="secondary"
            onClick={guard(async () => {
              const r = await api.chargeFees(fund.id);
              setNote(`Management fees charged: ${fmtMoney(r.charged)} (accrued to date, per LP).`);
            })}
          >
            Charge accrued fees
          </button>
        )}
      </div>

      <div className="tabs subtabs">
        {SUBTABS.map((t) => (
          <button
            key={t.key}
            className={sub === t.key ? "active" : ""}
            onClick={() => setSub(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>

      {sub === "capital" && (
        <>
          <div className="row">
            <div className="card" style={{ flex: 1 }}>
              <h3>Add LP</h3>
              <label>Name</label>
              <input value={lpName} onChange={(e) => setLpName(e.target.value)} />
              <label>Commitment (₹)</label>
              <input value={lpCommit} onChange={(e) => setLpCommit(e.target.value)} />
              <div style={{ marginTop: 10 }}>
                <button
                  disabled={!lpName || !lpCommit}
                  onClick={guard(async () => {
                    await api.addLP(fund.id, { name: lpName, commitment: lpCommit });
                    setLpName("");
                    setLpCommit("");
                  }, "LP added")}
                >
                  Add LP
                </button>
              </div>
            </div>

            <div className="card" style={{ flex: 1 }}>
              <h3>Capital call</h3>
              <label>% of commitment</label>
              <input value={callPct} onChange={(e) => setCallPct(e.target.value)} />
              <div style={{ marginTop: 10 }}>
                <button
                  disabled={lps.length === 0}
                  onClick={guard(() =>
                    api.createCall(fund.id, { pct: String(Number(callPct) / 100) }),
                    "Capital call issued"
                  )}
                >
                  Issue call
                </button>
              </div>
            </div>

            <div className="card" style={{ flex: 1 }}>
              <h3>Distribute</h3>
              <label>Gross amount (₹)</label>
              <input value={distAmt} onChange={(e) => setDistAmt(e.target.value)} />
              <label>Kind</label>
              <select value={distKind} onChange={(e) => setDistKind(e.target.value)}>
                <option value="profit">profit (carry applies)</option>
                <option value="return_of_capital">return of capital</option>
              </select>
              <div style={{ marginTop: 10 }}>
                <button
                  disabled={!distAmt}
                  onClick={guard(async () => {
                    await api.distribute(fund.id, { gross_amount: distAmt, kind: distKind });
                    setDistAmt("");
                  }, "Distribution recorded")}
                >
                  Record distribution
                </button>
              </div>
            </div>
          </div>

          <div className="card">
            <h3>
              Capital accounts{" "}
              <button
                className="secondary"
                style={{ marginLeft: 8 }}
                onClick={guard(async () => {
                  const now = new Date();
                  const qm = Math.floor(now.getMonth() / 3) * 3;
                  const iso = (d: Date) =>
                    `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
                  const start = await uiPrompt("Report period start (YYYY-MM-DD):", iso(new Date(now.getFullYear(), qm, 1)));
                  if (!start) return;
                  const end = await uiPrompt("Report period end (YYYY-MM-DD):", iso(new Date(now.getFullYear(), qm + 3, 0)));
                  if (!end) return;
                  const em = Number(end.slice(5, 7));
                  const ey = Number(end.slice(0, 4));
                  const label = `FY${(em >= 4 ? ey + 1 : ey) % 100} Q${em >= 4 ? Math.ceil((em - 3) / 3) : 4}`;
                  await api.lpReport(fund.id, { period_label: label, period_start: start, period_end: end });
                  setNote(`LP report ${label} generated — every LP sees it in their portal statements; it's also in Documents.`);
                }, "LP report generated")}
              >
                Quarterly LP report
              </button>{" "}
              <button
                className="secondary"
                title="On-screen magazine view of the quarterly report (last completed quarter)"
                onClick={guard(async () => {
                  setReportView(reportView ? null : await api.lpReportPreview(fund.id));
                })}
              >
                {reportView ? "Close report view" : "Report view"}
              </button>
            </h3>
            {reportView && (
              <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", background: "var(--light)", padding: 16, marginBottom: 12 }}>
                <LpReportView data={reportView} />
              </div>
            )}
            {accounts && accounts.accounts.length > 0 ? (
              <table>
                <thead>
                  <tr>
                    <th>LP</th>
                    <th>Committed</th>
                    <th>Drawn</th>
                    <th>Remaining</th>
                    <th>Distributed</th>
                    <th>Fees</th>
                    <th>Units</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {accounts.accounts.map((a) => (
                    <tr key={a.lp_id}>
                      <td>{a.lp_name}</td>
                      <td>{fmtMoney(a.committed)}</td>
                      <td>{fmtMoney(a.drawn)}</td>
                      <td>{fmtMoney(a.remaining)}</td>
                      <td>{fmtMoney(a.distributed)}</td>
                      <td>{fmtMoney(a.fees_charged)}</td>
                      <td>{fmtInt(a.units)}</td>
                      <td>
                        <button
                          className="secondary"
                          onClick={guard(async () => {
                            await api.lpStatement(fund.id, a.lp_id);
                            setNote(`Statement generated for ${a.lp_name} — it appears in their portal and in Documents.`);
                          }, "Statement generated")}
                        >
                          Statement
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <EmptyState icon="🤝" title="No LPs yet" hint="Add limited partners above (or convert prospects on the LP fundraise tab) to open capital accounts." />
            )}
          </div>

          <div className="card">
            <h3>Capital calls</h3>
            {calls.length === 0 && (
              <EmptyState icon="💸" title="No capital calls yet" hint="Issue a drawdown to call committed capital from the fund's LPs." />
            )}
            {calls.map((c) => (
              <div key={c.id} style={{ marginBottom: 10 }}>
                <strong>
                  Call #{c.call_no} — {(Number(c.pct) * 100).toFixed(0)}%
                </strong>
                <table>
                  <thead>
                    <tr><th>LP</th><th>Amount</th><th>Acknowledged</th><th>Status</th></tr>
                  </thead>
                  <tbody>
                    {c.notices.map((n) => (
                      <tr key={n.id}>
                        <td>{lps.find((l) => l.id === n.lp_id)?.name ?? n.lp_id}</td>
                        <td>{fmtMoney(n.amount)}</td>
                        <td>
                          {n.acknowledged_at ? (
                            <span className="badge">acknowledged</span>
                          ) : (
                            <span className="muted">not acknowledged</span>
                          )}
                        </td>
                        <td>
                          {n.paid ? (
                            <span className="badge complete">paid</span>
                          ) : (
                            <button
                              className="secondary"
                              onClick={guard(() => api.payNotice(fund.id, n.id), "Notice marked paid")}
                            >
                              Mark paid
                            </button>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
          </div>

          {dists.length > 0 && (
            <div className="card">
              <h3>
                Distributions (waterfall){" "}
                <button
                  className="secondary"
                  onClick={guard(async () => {
                    const fy = await uiPrompt("Financial year end (YYYY-MM-DD):", "2026-03-31");
                    if (!fy) return;
                    const r = await api.taxStatements(fund.id, fy);
                    setNote(`Generated Form 64D + ${r.form_64c} Form 64C statement(s) — ${fmtMoney(r.total_distributed)} distributed. LPs see their 64C in the portal.`);
                  })}
                >
                  Generate 64C / 64D
                </button>
              </h3>
              <p className="muted">
                Return of capital → preferred return ({(Number(fund.hurdle_pct) * 100).toFixed(0)}%) →
                GP catch-up → {(Number(fund.carry_pct) * 100).toFixed(0)}% carry.
              </p>
              <table>
                <thead>
                  <tr>
                    <th>#</th>
                    <th>Kind</th>
                    <th>Gross</th>
                    <th>Return of capital</th>
                    <th>Pref return</th>
                    <th>GP catch-up</th>
                    <th>GP total (carry)</th>
                    <th>Date</th>
                  </tr>
                </thead>
                <tbody>
                  {dists.map((d) => (
                    <tr key={d.id}>
                      <td>{d.dist_no}</td>
                      <td>{d.kind}</td>
                      <td>{fmtMoney(d.gross_amount)}</td>
                      <td>{fmtMoney(d.roc_amount)}</td>
                      <td>{fmtMoney(d.pref_amount)}</td>
                      <td>{fmtMoney(d.catchup_amount)}</td>
                      <td>{fmtMoney(d.carry_amount)}</td>
                      <td>{d.date ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ marginTop: 14 }}>
                <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
                  Waterfall by distribution — where each payout went
                </div>
                <ColumnChart
                  height={160}
                  format={(v) => fmtMoney(v)}
                  columns={dists.map((d) => {
                    const gross = Number(d.gross_amount);
                    const roc = Number(d.roc_amount);
                    const pref = Number(d.pref_amount);
                    const carry = Number(d.carry_amount);
                    return {
                      label: `#${d.dist_no}`,
                      segments: [
                        { label: "Return of capital", value: roc, color: "#4caf87" },
                        { label: "Preferred return", value: pref, color: "#c9a227" },
                        { label: "LP profit share", value: Math.max(0, gross - roc - pref - carry), color: "#2f6b52" },
                        { label: "GP carry (incl. catch-up)", value: carry, color: "#8a5a2b" },
                      ],
                    };
                  })}
                />
              </div>
            </div>
          )}
        </>
      )}

      {sub === "fundraise" && (
        <>
          <FundRaise fundId={fund.id} onChanged={() => refresh(fund.id)} />
          <FundDDQ fundId={fund.id} />
        </>
      )}

      {sub === "portfolio" && (
        <>
          <FundSignals fundId={fund.id} />

          <div className="card">
            <h3>Portfolio</h3>
            <div className="row">
              <input placeholder="Company" value={coName} onChange={(e) => setCoName(e.target.value)} />
              <input placeholder="Amount ₹" value={coAmt} onChange={(e) => setCoAmt(e.target.value)} />
              <input placeholder="Sector (segment)" value={coSector} onChange={(e) => setCoSector(e.target.value)} />
              <button
                style={{ flex: "0 0 auto" }}
                disabled={!coName}
                onClick={guard(async () => {
                  await api.addInvestment(fund.id, {
                    company_name: coName, amount: coAmt || "0", sector: coSector || null,
                  });
                  setCoName("");
                  setCoAmt("");
                  setCoSector("");
                }, "Investment added")}
              >
                Add investment
              </button>
            </div>
            {portfolio.length === 0 ? (
              <EmptyState icon="📊" title="No investments yet" hint="Add an investment above, or invest a deal from the Deal pipeline tab." />
            ) : (
              <table style={{ marginTop: 10 }}>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Instrument</th>
                    <th>Invested</th>
                    <th>Ownership %</th>
                    <th>Current value</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {portfolio.map((p) => (
                    <tr key={p.id}>
                      <td>{p.company_name}</td>
                      <td>{p.instrument}</td>
                      <td>{fmtMoney(p.amount)}</td>
                      <td>{p.ownership_pct}%</td>
                      <td>
                        {p.current_value ? (
                          <>{fmtMoney(p.current_value)} <span className="muted">({p.marked_on})</span></>
                        ) : (
                          <span className="muted">at cost</span>
                        )}
                      </td>
                      <td>
                        <button
                          className="secondary"
                          onClick={guard(async () => {
                            const v = await uiPrompt(`Mark ${p.company_name} — current fair value (₹):`, p.current_value ?? p.amount);
                            if (v) await api.markInvestment(fund.id, p.id, { current_value: v });
                          }, "Mark recorded")}
                        >
                          Mark
                        </button>{" "}
                        <button
                          className="secondary"
                          onClick={() => setOpenTear(openTear === p.id ? null : p.id)}
                        >
                          {openTear === p.id ? "Close" : "Tear sheet"}
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {openTear && (() => {
            const inv = portfolio.find((p) => p.id === openTear);
            if (!inv) return null;
            return (
              <TearSheet
                fundId={fund.id}
                inv={inv}
                soiRow={soi?.holdings.find((h) => h.id === inv.id) ?? null}
                onClose={() => setOpenTear(null)}
              />
            );
          })()}

          {soi && soi.holdings.length > 0 && (
            <div className="card">
              <h3>
                Schedule of Investments{" "}
                <button
                  className="secondary"
                  style={{ marginLeft: 8 }}
                  onClick={guard(async () => {
                    await api.soiReport(fund.id);
                    setNote("Schedule of Investments statement generated (see Documents).");
                  }, "SoI statement generated")}
                >
                  Generate statement
                </button>
              </h3>
              <p className="muted">
                Fair values are the fund's own marks; unmarked positions are held at cost.
              </p>
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Cost</th>
                    <th>Fair value</th>
                    <th>MOIC</th>
                    <th>Unrealised gain</th>
                    <th>% of NAV</th>
                  </tr>
                </thead>
                <tbody>
                  {soi.holdings.map((h) => (
                    <tr key={h.id}>
                      <td>
                        {h.company_name}{" "}
                        {!h.marked && <span className="badge">at cost</span>}
                      </td>
                      <td>{fmtMoney(h.cost)}</td>
                      <td>{fmtMoney(h.current_value)}</td>
                      <td>{h.moic ? `${h.moic}×` : "—"}</td>
                      <td className={Number(h.unrealized_gain) < 0 ? "delta-down" : "delta-up"}>
                        {fmtMoney(h.unrealized_gain)}
                      </td>
                      <td>{h.pct_of_nav}%</td>
                    </tr>
                  ))}
                  <tr style={{ fontWeight: 700, borderTop: "2px solid var(--border)" }}>
                    <td>Total ({soi.totals.count})</td>
                    <td>{fmtMoney(soi.totals.cost)}</td>
                    <td>{fmtMoney(soi.totals.current_value)}</td>
                    <td>{soi.totals.moic ? `${soi.totals.moic}×` : "—"}</td>
                    <td>{fmtMoney(soi.totals.unrealized_gain)}</td>
                    <td>100%</td>
                  </tr>
                </tbody>
              </table>
            </div>
          )}

          <FundValuations fundId={fund.id} onChanged={() => refresh(fund.id)} />

          <PortfolioMonitoring fundId={fund.id} />
        </>
      )}

      {sub === "deals" && (
        <>
          <DealPipeline fundId={fund.id} onInvested={() => refresh(fund.id)} />
          <FundNetwork fundId={fund.id} />
        </>
      )}

      {sub === "plan" && (
        <FundForecast fundId={fund.id} feePct={String(fund.mgmt_fee_pct)} carryPct={String(fund.carry_pct)} />
      )}

      {sub === "reports" && <FundFinancials fundId={fund.id} />}
    </div>
  );
}

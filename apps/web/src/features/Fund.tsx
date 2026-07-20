import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { uiPrompt } from "../components/Prompt";
import DealPipeline from "./DealPipeline";
import FundForecast from "./FundForecast";
import FundFinancials from "./FundFinancials";
import FundValuations from "./FundValuations";
import PortfolioMonitoring from "./PortfolioMonitoring";
import { useGuard } from "../hooks";
import {
  api,
  ApiError,
  type CapitalAccounts,
  type CapitalCall,
  type Distribution,
  type Fund as FundT,
  type FundPerformance,
  type LP,
  type PortfolioInvestment,
  type ScheduleOfInvestments,
} from "../api";

export default function Fund({ entityId }: { entityId: string }) {
  const [fund, setFund] = useState<FundT | null>(null);
  const [lps, setLps] = useState<LP[]>([]);
  const [calls, setCalls] = useState<CapitalCall[]>([]);
  const [dists, setDists] = useState<Distribution[]>([]);
  const [accounts, setAccounts] = useState<CapitalAccounts | null>(null);
  const [portfolio, setPortfolio] = useState<PortfolioInvestment[]>([]);
  const [soi, setSoi] = useState<ScheduleOfInvestments | null>(null);
  const [perf, setPerf] = useState<FundPerformance | null>(null);
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
    const [l, c, d, a, p, pf, s] = await Promise.all([
      api.listLPs(fid),
      api.listCalls(fid),
      api.listDistributions(fid),
      api.capitalAccounts(fid),
      api.listPortfolio(fid),
      api.fundPerformance(fid),
      api.scheduleOfInvestments(fid),
    ]);
    setLps(l);
    setCalls(c);
    setDists(d);
    setAccounts(a);
    setPortfolio(p);
    setPerf(pf);
    setSoi(s);
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
          <p className="muted">
            Committed ₹{accounts.totals.committed} · Drawn ₹{accounts.totals.drawn} · Remaining ₹
            {accounts.totals.remaining} · Distributed ₹{accounts.totals.distributed}
          </p>
        )}
        {perf && perf.paid_in !== "0.00" && (
          <p>
            <strong>Performance:</strong> DPI {perf.dpi ?? "—"} · RVPI {perf.rvpi ?? "—"} ·{" "}
            <strong>TVPI {perf.tvpi ?? "—"}</strong> · XIRR{" "}
            {perf.xirr_pct !== null ? `${perf.xirr_pct}%` : "—"} · NAV ₹{perf.nav}
            {perf.positions_at_cost > 0 && (
              <span className="muted"> ({perf.positions_at_cost} position(s) held at cost — mark them below)</span>
            )}
            <span className="muted"> · Management fee accrued ₹{perf.management_fee_accrued}</span>
            {perf.nav_per_unit && (
              <span className="muted"> · {perf.units_outstanding} units · NAV/unit ₹{perf.nav_per_unit}</span>
            )}
          </p>
        )}
        {perf && Number(perf.management_fee_accrued) > 0 && (
          <button
            className="secondary"
            onClick={guard(async () => {
              const r = await api.chargeFees(fund.id);
              setNote(`Management fees charged: ₹${r.charged} (accrued to date, per LP).`);
            })}
          >
            Charge accrued fees
          </button>
        )}
      </div>

      <FundForecast fundId={fund.id} feePct={String(fund.mgmt_fee_pct)} carryPct={String(fund.carry_pct)} />

      <FundFinancials fundId={fund.id} />

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
              })}
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
                api.createCall(fund.id, { pct: String(Number(callPct) / 100) })
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
              })}
            >
              Record distribution
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Capital accounts</h3>
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
                  <td>₹{a.committed}</td>
                  <td>₹{a.drawn}</td>
                  <td>₹{a.remaining}</td>
                  <td>₹{a.distributed}</td>
                  <td>₹{a.fees_charged}</td>
                  <td>{a.units}</td>
                  <td>
                    <button
                      className="secondary"
                      onClick={guard(async () => {
                        await api.lpStatement(fund.id, a.lp_id);
                        setNote(`Statement generated for ${a.lp_name} — it appears in their portal and in Documents.`);
                      })}
                    >
                      Statement
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : (
          <p className="muted">Add LPs to begin.</p>
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
              <tbody>
                {c.notices.map((n) => (
                  <tr key={n.id}>
                    <td>{lps.find((l) => l.id === n.lp_id)?.name ?? n.lp_id}</td>
                    <td>₹{n.amount}</td>
                    <td>
                      {n.paid ? (
                        <span className="badge complete">paid</span>
                      ) : (
                        <button
                          className="secondary"
                          onClick={guard(() => api.payNotice(fund.id, n.id))}
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
                setNote(`Generated Form 64D + ${r.form_64c} Form 64C statement(s) — ₹${r.total_distributed} distributed. LPs see their 64C in the portal.`);
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
                  <td>₹{d.gross_amount}</td>
                  <td>₹{d.roc_amount}</td>
                  <td>₹{d.pref_amount}</td>
                  <td>₹{d.catchup_amount}</td>
                  <td>₹{d.carry_amount}</td>
                  <td>{d.date ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="card">
        <h3>Portfolio</h3>
        <div className="row">
          <input placeholder="Company" value={coName} onChange={(e) => setCoName(e.target.value)} />
          <input placeholder="Amount ₹" value={coAmt} onChange={(e) => setCoAmt(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!coName}
            onClick={guard(async () => {
              await api.addInvestment(fund.id, { company_name: coName, amount: coAmt || "0" });
              setCoName("");
              setCoAmt("");
            })}
          >
            Add investment
          </button>
        </div>
        {portfolio.length > 0 && (
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
                  <td>₹{p.amount}</td>
                  <td>{p.ownership_pct}%</td>
                  <td>
                    {p.current_value ? (
                      <>₹{p.current_value} <span className="muted">({p.marked_on})</span></>
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
                      })}
                    >
                      Mark
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

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
              })}
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
                  <td>₹{h.cost}</td>
                  <td>₹{h.current_value}</td>
                  <td>{h.moic ? `${h.moic}×` : "—"}</td>
                  <td className={Number(h.unrealized_gain) < 0 ? "delta-down" : "delta-up"}>
                    ₹{h.unrealized_gain}
                  </td>
                  <td>{h.pct_of_nav}%</td>
                </tr>
              ))}
              <tr style={{ fontWeight: 700, borderTop: "2px solid var(--border)" }}>
                <td>Total ({soi.totals.count})</td>
                <td>₹{soi.totals.cost}</td>
                <td>₹{soi.totals.current_value}</td>
                <td>{soi.totals.moic ? `${soi.totals.moic}×` : "—"}</td>
                <td>₹{soi.totals.unrealized_gain}</td>
                <td>100%</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}

      <FundValuations fundId={fund.id} onChanged={() => refresh(fund.id)} />

      <PortfolioMonitoring fundId={fund.id} />

      <DealPipeline fundId={fund.id} onInvested={() => refresh(fund.id)} />
    </div>
  );
}

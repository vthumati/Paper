import { useEffect, useState } from "react";
import { api, type FundPlan } from "../api";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";
import Stat from "../components/Stat";

/** Fund construction & forecast (Carta "Fund Forecasting"): model how the fund
 * deploys — investable capital after fees, initial vs reserves, #deals, entry
 * ownership — with projected returns and year-by-year pacing, plus plan-vs-actual
 * read live from the portfolio and LP ledgers. */
export default function FundForecast({
  fundId,
  feePct,
  carryPct,
}: {
  fundId: string;
  feePct: string;
  carryPct: string;
}) {
  const [plan, setPlan] = useState<FundPlan | null>(null);
  const [open, setOpen] = useState(false);
  const { error, guard } = useGuard(() => load());

  // editable inputs (seeded from the server-computed plan/defaults)
  const [size, setSize] = useState("");
  const [life, setLife] = useState("10");
  const [invPeriod, setInvPeriod] = useState("4");
  const [expenses, setExpenses] = useState("0");
  const [reservePct, setReservePct] = useState("40");
  const [cheque, setCheque] = useState("");
  const [entryVal, setEntryVal] = useState("");
  const [moic, setMoic] = useState("3");

  function seed(p: FundPlan) {
    setPlan(p);
    const i = p.inputs;
    setSize(i.fund_size);
    setLife(String(i.fund_life_years));
    setInvPeriod(String(i.investment_period_years));
    setExpenses(i.est_expenses);
    setReservePct(String(Math.round(Number(i.reserve_pct) * 100)));
    setCheque(i.avg_initial_cheque);
    setEntryVal(i.avg_entry_valuation);
    setMoic(i.projected_gross_moic);
  }

  const load = () => api.fundPlan(fundId).then(seed);
  useEffect(() => {
    load();
  }, [fundId]);

  if (!plan) return null;
  const d = plan.derived;
  const a = plan.actual;
  const maxCum = Math.max(...plan.pacing.map((r) => Number(r.cumulative)), 1);

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>🧮</span> Fund construction &amp; forecast
        {!plan.has_plan && <span className="badge">not set</span>}
        <button className="secondary" style={{ marginLeft: "auto" }} onClick={() => setOpen((v) => !v)}>
          {open ? "Hide model" : "Edit model"}
        </button>
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Plan how the fund deploys and what it could return — a model, not a forecast. Fee{" "}
        {(Number(feePct) * 100).toFixed(1)}% and carry {(Number(carryPct) * 100).toFixed(0)}% come from the
        fund terms.
      </p>
      {error && <p className="error">{error}</p>}

      {open && (
        <div className="row" style={{ alignItems: "flex-end", marginBottom: 12 }}>
          <div><label>Fund size (₹)</label><input value={size} onChange={(e) => setSize(e.target.value)} /></div>
          <div><label>Fund life (yrs)</label><input value={life} onChange={(e) => setLife(e.target.value)} /></div>
          <div><label>Invest. period (yrs)</label><input value={invPeriod} onChange={(e) => setInvPeriod(e.target.value)} /></div>
          <div><label>Est. expenses (₹)</label><input value={expenses} onChange={(e) => setExpenses(e.target.value)} /></div>
          <div><label>Reserves (%)</label><input value={reservePct} onChange={(e) => setReservePct(e.target.value)} /></div>
          <div><label>Avg 1st cheque (₹)</label><input value={cheque} onChange={(e) => setCheque(e.target.value)} /></div>
          <div><label>Avg entry post-money (₹)</label><input value={entryVal} onChange={(e) => setEntryVal(e.target.value)} /></div>
          <div><label>Gross MOIC (×)</label><input value={moic} onChange={(e) => setMoic(e.target.value)} /></div>
          <button
            style={{ flex: "0 0 auto" }}
            onClick={guard(async () => {
              const p = await api.saveFundPlan(fundId, {
                fund_size: size || "0",
                fund_life_years: Number(life) || 10,
                investment_period_years: Number(invPeriod) || 4,
                est_expenses: expenses || "0",
                reserve_pct: String((Number(reservePct) || 0) / 100),
                avg_initial_cheque: cheque || "0",
                avg_entry_valuation: entryVal || "0",
                projected_gross_moic: moic || "0",
              });
              seed(p);
            })}
          >
            Save &amp; recalculate
          </button>
        </div>
      )}

      {/* capital plan */}
      <div className="stat-row" style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <Stat label="Investable capital" value={fmtMoney(d.investable)} hint="Fund size − lifetime management fees − estimated expenses" />
        <Stat label="Initial cheques" value={fmtMoney(d.initial_capital)} />
        <Stat label="Reserves (follow-on)" value={fmtMoney(d.reserve_capital)} />
        <Stat label="Initial deals" value={d.num_initial_deals} hint="Initial capital ÷ average first cheque" />
        <Stat label="Avg entry ownership" value={`${d.avg_entry_ownership_pct}%`} hint="Average first cheque ÷ average entry post-money" />
      </div>

      {/* projected returns */}
      <div className="stat-row" style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 10 }}>
        <Stat label="Gross MOIC" value={`${plan.inputs.projected_gross_moic}×`} />
        <Stat label="Gross TVPI" value={d.gross_tvpi ? `${d.gross_tvpi}×` : "—"} hint="Gross proceeds ÷ fund size" />
        <Stat label="Net TVPI to LPs" value={d.net_tvpi ? `${d.net_tvpi}×` : "—"} big hint="After GP carry on profit over committed capital" />
        <Stat label="≈ Net IRR" value={d.net_irr_pct !== null ? `${d.net_irr_pct}%` : "—"} hint="Rough estimate from net TVPI over ~60% of fund life; no cashflow timing" />
        <Stat label="GP carry" value={fmtMoney(d.gp_carry)} />
      </div>

      {/* deployment pacing */}
      <div style={{ marginTop: 16 }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
          Deployment pacing — cumulative capital deployed over the {plan.inputs.investment_period_years}-year
          investment period
        </div>
        <div style={{ display: "flex", alignItems: "flex-end", gap: 10, height: 120 }}>
          {plan.pacing.map((r) => (
            <div key={r.year} style={{ flex: 1, textAlign: "center" }}>
              <div style={{ fontSize: 11, color: "var(--muted)", marginBottom: 4 }}>
                {fmtMoney(r.cumulative)}
              </div>
              <div
                title={`Year ${r.year}: deployed ${fmtMoney(r.deployed)} (cumulative ${fmtMoney(r.cumulative)})`}
                style={{
                  height: `${Math.max((Number(r.cumulative) / maxCum) * 84, 3)}px`,
                  background: "var(--navy)",
                  borderRadius: "5px 5px 0 0",
                }}
              />
              <div style={{ fontSize: 11, color: "var(--muted)", marginTop: 4 }}>Yr {r.year}</div>
            </div>
          ))}
        </div>
      </div>

      {/* plan vs actual */}
      <div style={{ marginTop: 8, paddingTop: 12, borderTop: "1px solid var(--border)" }}>
        <div className="muted" style={{ fontSize: 12, marginBottom: 8 }}>Plan vs. actual (live)</div>
        <div className="row">
          <Progress label="Committed vs. target" pct={a.committed_vs_target_pct}
            detail={`${fmtMoney(a.committed)} of ${fmtMoney(plan.inputs.fund_size)}`} />
          <Progress label="Deployed vs. initial capital" pct={a.deployed_vs_initial_pct}
            detail={`${fmtMoney(a.deployed)} of ${fmtMoney(d.initial_capital)}`} />
          <Progress label="Deals vs. plan" pct={a.deals_vs_plan_pct}
            detail={`${a.deals} of ${d.num_initial_deals}`} />
        </div>
      </div>
    </div>
  );
}

function Progress({ label, pct, detail }: { label: string; pct: number | null; detail: string }) {
  const shown = Math.min(Math.max(pct ?? 0, 0), 100);
  return (
    <div style={{ flex: 1, minWidth: 180 }}>
      <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12 }}>
        <span style={{ color: "var(--heading)", fontWeight: 600 }}>{label}</span>
        <span className="num" style={{ color: "var(--muted)" }}>{pct !== null ? `${pct}%` : "—"}</span>
      </div>
      <div style={{ height: 8, background: "var(--light)", borderRadius: 5, overflow: "hidden", margin: "5px 0 3px" }}>
        <div style={{ width: `${shown}%`, height: "100%", background: "var(--ok, #2f7d5b)", borderRadius: 5 }} />
      </div>
      <div className="muted" style={{ fontSize: 11 }}>{detail}</div>
    </div>
  );
}

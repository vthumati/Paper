import { useEffect, useState } from "react";
import { fmtMoney } from "../lib/format";
import {
  api,
  type ScorecardFactor,
  type ValuationEstimate,
  type ValuationEstimateResult,
} from "../api";

type Method = "scorecard" | "vc_method" | "dcf";
const METHOD_LABEL: Record<Method, string> = {
  scorecard: "Scorecard",
  vc_method: "VC method",
  dcf: "Discounted cash flow",
};

interface ProjRow {
  revenue: string;
  expenses: string;
}

/** Self-serve indicative valuation (FR-L-2): pick any of scorecard / VC method
 * / DCF, weight them, preview or save; smartfill DCF from financials. */
export default function StartupValuation({
  entityId,
  onSaved,
}: {
  entityId: string;
  onSaved?: () => void;
}) {
  const [factors, setFactors] = useState<ScorecardFactor[]>([]);
  const [saved, setSaved] = useState<ValuationEstimate[]>([]);
  const [error, setError] = useState("");
  const [result, setResult] = useState<ValuationEstimateResult | null>(null);

  const [label, setLabel] = useState("Working estimate");
  const [enabled, setEnabled] = useState<Record<Method, boolean>>({
    scorecard: true,
    vc_method: false,
    dcf: false,
  });
  const [weights, setWeights] = useState<Record<Method, string>>({
    scorecard: "1",
    vc_method: "1",
    dcf: "1",
  });

  // scorecard inputs
  const [baseVal, setBaseVal] = useState("40000000");
  const [scores, setScores] = useState<Record<string, string>>({});
  // vc-method inputs
  const [exitValue, setExitValue] = useState("500000000");
  const [targetMultiple, setTargetMultiple] = useState("10");
  const [plannedRaise, setPlannedRaise] = useState("20000000");
  // dcf inputs
  const [discountRate, setDiscountRate] = useState("25");
  const [terminalGrowth, setTerminalGrowth] = useState("3");
  const [proj, setProj] = useState<ProjRow[]>([
    { revenue: "10000000", expenses: "8000000" },
    { revenue: "18000000", expenses: "12000000" },
    { revenue: "30000000", expenses: "18000000" },
  ]);

  function load() {
    api.scorecardFactors(entityId).then((r) => setFactors(r.factors)).catch(() => {});
    api.listValuationEstimates(entityId).then(setSaved).catch((e) => setError(e.message));
  }
  useEffect(load, [entityId]);

  function buildBody(save: boolean) {
    const body: Record<string, unknown> = {
      label,
      save,
      weights: Object.fromEntries(
        (Object.keys(enabled) as Method[]).filter((m) => enabled[m]).map((m) => [m, weights[m]])
      ),
    };
    if (enabled.scorecard) body.scorecard = { base_valuation: baseVal, scores };
    if (enabled.vc_method)
      body.vc_method = {
        exit_value: exitValue,
        target_multiple: targetMultiple,
        planned_raise: plannedRaise,
      };
    if (enabled.dcf)
      body.dcf = {
        projections: proj.map((p) => ({ revenue: p.revenue, expenses: p.expenses })),
        discount_rate_pct: discountRate,
        terminal_growth_pct: terminalGrowth,
      };
    return body;
  }

  async function run(save: boolean) {
    setError("");
    try {
      const est = await api.createValuationEstimate(entityId, buildBody(save));
      setResult(est.results);
      if (save) {
        load();
        onSaved?.();
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function smartfill() {
    setError("");
    try {
      const s = await api.valuationSmartfill(entityId, 25, 5);
      setProj(s.projections.map((p) => ({ revenue: p.revenue, expenses: p.expenses })));
      setEnabled((e) => ({ ...e, dcf: true }));
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const toggle = (m: Method) => setEnabled((e) => ({ ...e, [m]: !e[m] }));

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>Indicative valuation</h2>
        <p className="muted">
          A self-serve estimate blending the methods you choose — indicative only, a supporting
          workpaper for a Rule 11UA / registered-valuer engagement, not a substitute for it.
        </p>
        <label>Scenario name</label>
        <input value={label} onChange={(e) => setLabel(e.target.value)} style={{ maxWidth: 300 }} />

        <div className="row" style={{ gap: 8, marginTop: 12 }}>
          {(Object.keys(METHOD_LABEL) as Method[]).map((m) => (
            <label key={m} style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input
                type="checkbox"
                style={{ width: "auto" }}
                checked={enabled[m]}
                onChange={() => toggle(m)}
              />
              {METHOD_LABEL[m]}
              {enabled[m] && (
                <input
                  title="weight"
                  value={weights[m]}
                  onChange={(e) => setWeights((w) => ({ ...w, [m]: e.target.value }))}
                  style={{ width: 50, marginLeft: 4 }}
                />
              )}
            </label>
          ))}
        </div>
      </div>

      {enabled.scorecard && (
        <div className="card">
          <h3>Scorecard method</h3>
          <label>Benchmark pre-money for the region / stage (₹)</label>
          <input value={baseVal} onChange={(e) => setBaseVal(e.target.value)} style={{ maxWidth: 240 }} />
          <p className="muted" style={{ marginTop: 8 }}>
            Score each factor vs a typical company (100 = at benchmark, 120 = 20% stronger).
          </p>
          <table>
            <thead>
              <tr><th>Factor</th><th>Weight</th><th>Score</th></tr>
            </thead>
            <tbody>
              {factors.map((f) => (
                <tr key={f.key}>
                  <td>{f.label}</td>
                  <td>{(Number(f.weight) * 100).toFixed(0)}%</td>
                  <td>
                    <input
                      value={scores[f.key] ?? "100"}
                      onChange={(e) => setScores((s) => ({ ...s, [f.key]: e.target.value }))}
                      style={{ width: 70 }}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {enabled.vc_method && (
        <div className="card">
          <h3>VC method</h3>
          <div className="row">
            <div>
              <label>Projected exit value (₹)</label>
              <input value={exitValue} onChange={(e) => setExitValue(e.target.value)} />
            </div>
            <div>
              <label>Target return multiple (×)</label>
              <input value={targetMultiple} onChange={(e) => setTargetMultiple(e.target.value)} />
            </div>
            <div>
              <label>Planned raise this round (₹)</label>
              <input value={plannedRaise} onChange={(e) => setPlannedRaise(e.target.value)} />
            </div>
          </div>
        </div>
      )}

      {enabled.dcf && (
        <div className="card">
          <h3>
            Discounted cash flow{" "}
            <button className="secondary" style={{ marginLeft: 8 }} onClick={smartfill}>
              Smartfill from financials
            </button>
          </h3>
          <div className="row">
            <div>
              <label>Discount rate (%)</label>
              <input value={discountRate} onChange={(e) => setDiscountRate(e.target.value)} />
            </div>
            <div>
              <label>Terminal growth (%)</label>
              <input value={terminalGrowth} onChange={(e) => setTerminalGrowth(e.target.value)} />
            </div>
          </div>
          <table>
            <thead>
              <tr><th>Year</th><th>Revenue (₹)</th><th>Expenses (₹)</th></tr>
            </thead>
            <tbody>
              {proj.map((p, i) => (
                <tr key={i}>
                  <td>{i + 1}</td>
                  <td>
                    <input
                      value={p.revenue}
                      onChange={(e) =>
                        setProj((rows) => rows.map((r, j) => (j === i ? { ...r, revenue: e.target.value } : r)))
                      }
                    />
                  </td>
                  <td>
                    <input
                      value={p.expenses}
                      onChange={(e) =>
                        setProj((rows) => rows.map((r, j) => (j === i ? { ...r, expenses: e.target.value } : r)))
                      }
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button
            className="secondary"
            onClick={() => setProj((r) => [...r, { revenue: "0", expenses: "0" }])}
          >
            + year
          </button>
        </div>
      )}

      <div className="card">
        <button onClick={() => run(false)}>Preview</button>{" "}
        <button className="secondary" onClick={() => run(true)}>Save estimate</button>
        {result && (
          <div style={{ marginTop: 12 }}>
            <table>
              <tbody>
                {Object.entries(result.methods).map(([m, v]) => (
                  <tr key={m}>
                    <td>{METHOD_LABEL[m as Method] ?? m}</td>
                    <td>{fmtMoney(v)}</td>
                    <td className="muted">
                      weight {(Number(result.weights[m]) * 100).toFixed(0)}%
                    </td>
                  </tr>
                ))}
                <tr style={{ fontWeight: 700, borderTop: "2px solid var(--border)" }}>
                  <td>Blended value</td>
                  <td>{fmtMoney(result.blended_value)}</td>
                  <td className="muted">{result.fd_shares.toLocaleString()} FD shares</td>
                </tr>
                {result.per_share && (
                  <tr style={{ fontWeight: 700 }}>
                    <td>Indicative per share</td>
                    <td>{fmtMoney(result.per_share)}</td>
                    <td></td>
                  </tr>
                )}
              </tbody>
            </table>
            <p className="muted" style={{ marginTop: 8 }}>{result.disclaimer}</p>
          </div>
        )}
      </div>

      {saved.length > 0 && (
        <div className="card">
          <h3>Saved estimates</h3>
          <table>
            <thead>
              <tr><th>Scenario</th><th>Blended</th><th>Per share</th><th>Saved</th><th></th></tr>
            </thead>
            <tbody>
              {saved.map((e) => (
                <tr key={e.id}>
                  <td>{e.label}</td>
                  <td>{fmtMoney(e.results.blended_value)}</td>
                  <td>{e.results.per_share ? `₹${e.results.per_share}` : "—"}</td>
                  <td className="muted">{new Date(e.created_at).toLocaleDateString()}</td>
                  <td>
                    <button
                      className="secondary"
                      onClick={() =>
                        api
                          .valuationEstimateReport(entityId, e.id)
                          .catch((err) => setError((err as Error).message))
                          .then(() => setError(""))
                      }
                    >
                      Generate workpaper
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

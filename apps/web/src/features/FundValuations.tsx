import { useEffect, useState } from "react";
import { api, type ValuationSummary } from "../api";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";
import Stat from "../components/Stat";

const todayIso = () => new Date().toISOString().slice(0, 10);

/** SEBI independent portfolio valuation (FR-J-15): a valuation policy (appointed
 * valuer + frequency), per-holding valuation records with methodology and an
 * independence flag, staleness against the policy frequency, and a valuation
 * report. The latest valuation becomes the holding's mark. */
export default function FundValuations({
  fundId,
  onChanged,
}: {
  fundId: string;
  onChanged?: () => void;
}) {
  const [sum, setSum] = useState<ValuationSummary | null>(null);
  const [recording, setRecording] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const { error, guard } = useGuard(() => load());

  // policy
  const [valuer, setValuer] = useState("");
  const [freq, setFreq] = useState("12");
  // record form
  const [value, setValue] = useState("");
  const [asOf, setAsOf] = useState(todayIso());
  const [method, setMethod] = useState("ipev_market");
  const [rValuer, setRValuer] = useState("");
  const [indep, setIndep] = useState(true);

  const load = () =>
    api.valuationSummary(fundId).then((s) => {
      setSum(s);
      setValuer(s.policy.valuer_name ?? "");
      setFreq(String(s.policy.frequency_months));
      if (!rValuer && s.policy.valuer_name) setRValuer(s.policy.valuer_name);
    });
  useEffect(() => {
    load();
  }, [fundId]);

  if (!sum) return null;
  const t = sum.totals;
  const methods = Object.entries(sum.methodologies);

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>⚖️</span> Portfolio valuation
        {t.stale > 0 && <span className="badge danger">{t.stale} stale</span>}
        <button
          className="secondary"
          style={{ marginLeft: "auto" }}
          onClick={guard(async () => {
            await api.valuationReport(fundId);
            setNote("Valuation report generated (see Documents).");
          }, "Valuation report generated")}
          disabled={sum.holdings.length === 0}
        >
          Generate report
        </button>
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        SEBI AIF holdings need independent valuation at set intervals. Record a valuation per holding;
        the latest becomes its mark. Holdings past the policy frequency are flagged stale.
      </p>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      {/* policy */}
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div><label>Independent valuer</label><input placeholder="e.g. Kroll India" value={valuer} onChange={(e) => setValuer(e.target.value)} /></div>
        <div style={{ flex: "0 0 160px" }}>
          <label>Valuation frequency (months)</label>
          <input value={freq} onChange={(e) => setFreq(e.target.value)} />
        </div>
        <button
          style={{ flex: "0 0 auto" }}
          onClick={guard(async () => {
            await api.setValuationPolicy(fundId, {
              valuer_name: valuer || null,
              valuation_frequency_months: Number(freq) || 12,
            });
          }, "Valuation policy saved")}
        >
          Save policy
        </button>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10, marginTop: 12 }}>
        <Stat label="Holdings valued" value={`${t.valued} / ${t.holdings}`} />
        <Stat label="Independently" value={t.independent} hint="Latest valuation marked as done by an independent valuer" />
        <Stat label="Stale" value={t.stale} alert={t.stale > 0} hint={`Latest valuation older than ${sum.policy.frequency_months} months`} />
      </div>

      {sum.holdings.length > 0 && (
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>Company</th><th>Cost</th><th>Latest value</th><th>Methodology</th>
              <th>Valuer</th><th>As of</th><th></th>
            </tr>
          </thead>
          <tbody>
            {sum.holdings.map((h) => (
              <tr key={h.investment_id}>
                <td>{h.company_name}</td>
                <td>{fmtMoney(h.cost)}</td>
                <td>{h.latest ? fmtMoney(h.latest.value) : <span className="muted">—</span>}</td>
                <td>{h.latest ? h.latest.methodology_label : <span className="muted">—</span>}</td>
                <td>
                  {h.latest ? (
                    <>
                      {h.latest.valuer ?? <span className="muted">—</span>}{" "}
                      {h.latest.is_independent && <span className="badge complete">independent</span>}
                    </>
                  ) : (
                    <span className="muted">—</span>
                  )}
                </td>
                <td>
                  {h.latest ? h.latest.as_of : <span className="muted">not valued</span>}{" "}
                  {h.stale && <span className="badge danger">stale</span>}
                </td>
                <td>
                  <button
                    className="secondary"
                    onClick={() => {
                      setRecording(recording === h.investment_id ? null : h.investment_id);
                      setValue(h.latest?.value ?? h.cost);
                    }}
                  >
                    {recording === h.investment_id ? "Cancel" : "Value"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {recording && (
        <div className="row" style={{ alignItems: "flex-end", marginTop: 12 }}>
          <div><label>Fair value (₹)</label><input value={value} onChange={(e) => setValue(e.target.value)} /></div>
          <div><label>As of</label><input type="date" value={asOf} onChange={(e) => setAsOf(e.target.value)} /></div>
          <div>
            <label>Methodology</label>
            <select value={method} onChange={(e) => setMethod(e.target.value)}>
              {methods.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
            </select>
          </div>
          <div><label>Valuer</label><input value={rValuer} onChange={(e) => setRValuer(e.target.value)} /></div>
          <label style={{ flex: "0 0 auto", display: "flex", alignItems: "center", gap: 4 }}>
            <input type="checkbox" style={{ width: "auto" }} checked={indep} onChange={(e) => setIndep(e.target.checked)} />
            independent
          </label>
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!value}
            onClick={guard(async () => {
              await api.recordValuation(fundId, recording, {
                as_of: asOf,
                value,
                methodology: method,
                valuer: rValuer || null,
                is_independent: indep,
              });
              setRecording(null);
              setValue("");
              onChanged?.();
            }, "Valuation recorded")}
          >
            Record valuation
          </button>
        </div>
      )}
    </div>
  );
}

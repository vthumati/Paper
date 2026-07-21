import { useEffect, useState } from "react";
import { api, type PortfolioSignals } from "../api";
import Stat from "../components/Stat";

const SEVERITY_BADGE: Record<string, string> = {
  high: "danger",
  warn: "active",
  info: "skipped",
  positive: "complete",
};
const SEVERITY_ICON: Record<string, string> = {
  high: "🔴",
  warn: "🟠",
  info: "ℹ️",
  positive: "🌱",
};
// render order: worst first, opportunities last
const SEVERITY_ORDER = ["high", "warn", "info", "positive"];
// Vestberry-style attention-list row tints (full-row wash by severity)
const SEVERITY_ROW_BG: Record<string, string> = {
  high: "rgba(200, 60, 60, 0.09)",
  warn: "rgba(210, 140, 40, 0.10)",
  info: "rgba(120, 120, 120, 0.07)",
  positive: "rgba(60, 150, 90, 0.09)",
};

/** Portfolio signals (Vestberry-style early warning): rules over the KPI
 * history and marks — revenue decline, low runway, impaired marks, reporting
 * gone silent — plus follow-on candidates. Read-only derivation. */
export default function FundSignals({ fundId }: { fundId: string }) {
  const [sig, setSig] = useState<PortfolioSignals | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.portfolioSignals(fundId).then(setSig).catch((e) => setError(e.message));
  }, [fundId]);

  if (!sig) return null;
  const t = sig.totals;
  const rows = sig.companies
    .flatMap((c) => c.signals.map((s) => ({ ...s, company: c.company_name })))
    .sort((a, b) => SEVERITY_ORDER.indexOf(a.severity) - SEVERITY_ORDER.indexOf(b.severity));

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>🚨</span> Signals
        {t.high > 0 && <span className="badge danger">{t.high} high</span>}
        {t.positive > 0 && <span className="badge complete">{t.positive} follow-on</span>}
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Early warnings derived from reported KPIs and marks — declining revenue, short runway,
        impaired marks, reporting gaps — and which companies look ready for follow-on capital.
      </p>
      {error && <p className="error">{error}</p>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <Stat label="High severity" value={t.high} alert={t.high > 0} />
        <Stat label="Warnings" value={t.warn} />
        <Stat label="Follow-on candidates" value={t.positive} hint="Growing revenue with 12+ months of runway" />
        <Stat label="All clear" value={t.clear} hint="Companies with no active signals" />
      </div>

      {rows.length === 0 ? (
        <p className="muted" style={{ marginTop: 12 }}>
          ✓ No signals — the portfolio looks healthy on the latest reported data.
        </p>
      ) : (
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr><th></th><th>Company</th><th>Signal</th><th>Detail</th></tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} style={{ background: SEVERITY_ROW_BG[r.severity] }}>
                <td style={{ width: 30 }}>{SEVERITY_ICON[r.severity]}</td>
                <td>{r.company}</td>
                <td><span className={`badge ${SEVERITY_BADGE[r.severity]}`}>{r.kind.replace(/_/g, " ")}</span></td>
                <td className="muted">{r.message}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

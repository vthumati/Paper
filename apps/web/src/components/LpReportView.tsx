import type { LpReportData } from "../api";
import { fmtMoney } from "../lib/format";

/** Rundit-style magazine rendering of the quarterly LP report — big serif
 * figures with growth arrows, section by section. Shared by the GP preview
 * (Fund workspace) and the LP portal. */

function Figure({ label, value, arrow }: { label: string; value: string; arrow?: boolean }) {
  return (
    <div style={{ minWidth: 170 }}>
      <div className="muted" style={{ fontSize: 11, textTransform: "uppercase", letterSpacing: "0.07em" }}>
        {label}
      </div>
      <div style={{ fontFamily: "var(--serif, Georgia, serif)", fontSize: 30, color: "var(--green, #1e6b3f)", lineHeight: 1.25 }}>
        {value}
        {arrow && <span style={{ fontSize: 20 }}> ↗</span>}
      </div>
    </div>
  );
}

function SectionTitle({ children }: { children: string }) {
  return (
    <h2 style={{ fontFamily: "var(--serif, Georgia, serif)", fontSize: 26, margin: "22px 0 10px", color: "var(--heading)" }}>
      {children}
    </h2>
  );
}

export default function LpReportView({ data }: { data: LpReportData }) {
  const p = data.performance;
  const active = data.holdings.length;
  return (
    <div style={{ maxWidth: 860 }}>
      <div className="muted" style={{ fontSize: 12, display: "flex", gap: 14, flexWrap: "wrap" }}>
        <span>TITLE: <strong>{data.period_label} report</strong></span>
        <span>FUND: <strong>{data.fund_name}</strong> (SEBI Cat {data.category})</span>
        <span>PERIOD: {data.period_start} → {data.period_end}</span>
        <span>PREPARED: {data.prepared_on}</span>
      </div>

      <SectionTitle>Fund Summary</SectionTitle>
      <div style={{ display: "flex", flexWrap: "wrap", gap: "14px 34px" }}>
        <Figure label="Committed" value={fmtMoney(data.snapshot.committed)} />
        <Figure label="Paid in" value={fmtMoney(data.snapshot.drawn)} />
        <Figure label="Uncalled" value={fmtMoney(data.snapshot.remaining)} />
        <Figure label="Distributed" value={fmtMoney(data.snapshot.distributed)} />
        <Figure label="NAV" value={fmtMoney(p.nav)} />
        {p.tvpi && <Figure label="TVPI (×)" value={p.tvpi} arrow={Number(p.tvpi) > 1} />}
        {p.dpi && <Figure label="DPI (×)" value={p.dpi} />}
        {p.xirr_pct !== null && <Figure label="XIRR" value={`${p.xirr_pct}%`} arrow={p.xirr_pct > 0} />}
        {p.nav_per_unit && <Figure label="NAV / unit" value={`₹${p.nav_per_unit}`} />}
      </div>

      <SectionTitle>Activity This Period</SectionTitle>
      {data.activity.capital_calls.length === 0 && data.activity.distributions.length === 0 ? (
        <p className="muted">No capital calls or distributions this period.</p>
      ) : (
        <ul className="muted" style={{ lineHeight: 1.7 }}>
          {data.activity.capital_calls.map((c) => (
            <li key={`c${c.call_no}`}>
              Capital call #{c.call_no} ({c.date ?? "—"}): <strong>{fmtMoney(c.amount)}</strong>
              {c.purpose && <> — {c.purpose}</>}
            </li>
          ))}
          {data.activity.distributions.map((d) => (
            <li key={`d${d.dist_no}`}>
              Distribution #{d.dist_no} ({d.date ?? "—"}): <strong>{fmtMoney(d.gross_amount)}</strong> gross
              ({d.kind}, carry {fmtMoney(d.carry_amount)})
            </li>
          ))}
        </ul>
      )}

      <SectionTitle>Active Companies</SectionTitle>
      <p className="muted" style={{ marginTop: 0 }}>
        {active} compan{active === 1 ? "y" : "ies"} · total cost {fmtMoney(data.totals.cost)} · fair value{" "}
        {fmtMoney(data.totals.current_value)}
        {data.totals.moic && <> · blended MOIC {data.totals.moic}×</>}
      </p>
      {data.holdings.map((h) => (
        <div
          key={h.id}
          style={{ borderTop: "1px solid var(--border)", padding: "12px 0", display: "flex", gap: 24, flexWrap: "wrap" }}
        >
          <div style={{ flex: "0 0 200px" }}>
            <div style={{ fontFamily: "var(--serif, Georgia, serif)", fontSize: 19, color: "var(--heading)" }}>
              {h.company_name}
            </div>
            <div className="muted" style={{ fontSize: 12 }}>
              {h.instrument}
              {h.invested_on && <> · since {h.invested_on}</>}
              {h.holding_years !== null && <> · {h.holding_years} yrs</>}
            </div>
          </div>
          <div style={{ flex: 1, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(140px, 1fr))", gap: "4px 16px", fontSize: 13 }}>
            <span className="muted">Ownership <strong style={{ color: "var(--heading)" }}>{h.ownership_pct}%</strong></span>
            <span className="muted">Invested <strong style={{ color: "var(--heading)" }}>{fmtMoney(h.cost)}</strong></span>
            <span className="muted">Fair value <strong style={{ color: "var(--heading)" }}>{fmtMoney(h.current_value)}</strong></span>
            <span className="muted">MOIC <strong style={{ color: "var(--heading)" }}>{h.moic ? `${h.moic}×` : "—"}</strong></span>
            <span className="muted">
              FV growth{" "}
              {h.gain_pct === null ? (
                <strong style={{ color: "var(--heading)" }}>—</strong>
              ) : (
                <span
                  className="badge"
                  style={{
                    background: h.gain_pct >= 0 ? "rgba(47,125,91,0.15)" : "rgba(179,66,58,0.15)",
                    color: h.gain_pct >= 0 ? "var(--green, #1e6b3f)" : "#b3423a",
                  }}
                >
                  {h.gain_pct >= 0 ? "▲" : "▼"} {Math.abs(h.gain_pct)}%
                </span>
              )}
            </span>
            {!h.marked && <span className="muted" style={{ fontSize: 11 }}>held at cost</span>}
          </div>
        </div>
      ))}

      <SectionTitle>Valuation Status</SectionTitle>
      <p className="muted">
        {data.valuation_status.valued} of {data.valuation_status.holdings} holdings valued ·{" "}
        {data.valuation_status.independent} independently · {data.valuation_status.stale} stale vs policy.
        Figures are unaudited; fair values per the fund's marks and valuation policy.
      </p>
    </div>
  );
}

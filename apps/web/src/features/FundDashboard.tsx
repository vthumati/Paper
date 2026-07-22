import { useEffect, useState } from "react";
import { api, type Dashboard } from "../api";
import Stat from "../components/Stat";
import PageHeader from "../components/PageHeader";
import { fmtMoney } from "../lib/format";

/** Fund-first home for AIF/fund entities — a fund summary and quick actions
 * instead of the startup cap-table dashboard. */
export default function FundDashboard({
  entityId,
  onNavigate,
}: {
  entityId: string;
  onNavigate: (tab: string) => void;
}) {
  const [d, setD] = useState<Dashboard | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboard(entityId).then(setD).catch((e) => setError((e as Error).message));
  }, [entityId]);

  if (error) return <p className="error">{error}</p>;
  if (!d) return <p>Loading…</p>;
  const f = d.fund;
  if (!f) return <p className="muted">This entity has no fund profile yet.</p>;

  const pct = (v: string, dp = 0) => `${(Number(v) * 100).toFixed(dp)}%`;
  const overdue = d.compliance.overdue;

  return (
    <div>
      <PageHeader
        icon="🏦"
        title="Fund"
        subtitle="Commitments, NAV and portfolio at a glance."
      />
      <p className="muted" style={{ marginTop: 0 }}>
        SEBI Cat {f.sebi_category} · carry {pct(f.carry_pct)} · hurdle {pct(f.hurdle_pct)} · fee{" "}
        {pct(f.mgmt_fee_pct, 1)} on committed
      </p>

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <Stat label="Committed" value={fmtMoney(f.committed)} big />
        <Stat label="Drawn" value={fmtMoney(f.drawn)} />
        <Stat label="Uncalled" value={fmtMoney(f.uncalled)} />
        <Stat label="Distributed" value={fmtMoney(f.distributed)} />
        <Stat label="NAV" value={fmtMoney(f.nav)} />
        <Stat label="TVPI" value={`${f.tvpi}×`} />
        <Stat label="DPI" value={`${f.dpi}×`} />
        <Stat label="LPs" value={f.lps} />
        <Stat label="Portfolio companies" value={f.portfolio_count} />
      </div>

      <div className="card">
        <h3 style={{ marginTop: 0 }}>Manage the fund</h3>
        <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
          <button style={{ flex: "0 0 auto" }} onClick={() => onNavigate("capital")}>
            Capital & LPs
          </button>
          <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => onNavigate("deals")}>
            Deal pipeline
          </button>
          <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => onNavigate("portfolio")}>
            Portfolio
          </button>
          <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => onNavigate("monitoring")}>
            Monitoring
          </button>
          <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => onNavigate("fundraise")}>
            LP fundraise
          </button>
          <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => onNavigate("reports")}>
            Financials
          </button>
        </div>
      </div>

      {overdue > 0 && (
        <div className="card" style={{ borderLeft: "4px solid var(--warn)" }}>
          <p style={{ margin: 0 }}>
            <strong>{overdue}</strong> overdue compliance obligation{overdue > 1 ? "s" : ""}.{" "}
            <button className="secondary" onClick={() => onNavigate("compliance")}>
              Open Compliance
            </button>
          </p>
        </div>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, type Dashboard as DashboardT } from "../api";

import Stat from "../components/Stat";

export default function Dashboard({ entityId }: { entityId: string }) {
  const [d, setD] = useState<DashboardT | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboard(entityId).then(setD).catch((e) => setError(e.message));
  }, [entityId]);

  if (error) return <p className="error">{error}</p>;
  if (!d) return <p className="muted">Loading…</p>;

  return (
    <div>
      <div className="card">
        <h2>Overview</h2>
        <div className="row" style={{ gap: 10 }}>
          <Stat label="Shares issued" value={d.cap_table.total_shares.toLocaleString()} />
          <Stat label="Stakeholders" value={d.cap_table.holders} />
          <Stat label="Capital raised (₹)" value={d.cap_table.total_invested} />
          <Stat label="Documents" value={d.documents} />
          <Stat label="Data rooms" value={d.data_rooms} />
        </div>
      </div>

      <div className="row" style={{ gap: 10 }}>
        <div className="card" style={{ flex: 1 }}>
          <h3>Fundraising</h3>
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Rounds" value={d.fundraising.rounds} />
            <Stat label="Open" value={d.fundraising.open_rounds} />
          </div>
        </div>
        <div className="card" style={{ flex: 1 }}>
          <h3>Compliance</h3>
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Obligations" value={d.compliance.total} />
            <Stat label="Overdue" value={d.compliance.overdue} alert={d.compliance.overdue > 0} />
          </div>
        </div>
      </div>

      <div className="row" style={{ gap: 10 }}>
        <div className="card" style={{ flex: 1 }}>
          <h3>ESOP</h3>
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Schemes" value={d.esop.schemes} />
            <Stat label="Options granted" value={d.esop.options_granted.toLocaleString()} />
          </div>
        </div>
        <div className="card" style={{ flex: 1 }}>
          <h3>Governance</h3>
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Meetings" value={d.governance.meetings} />
            <Stat
              label="Pending resolutions"
              value={d.governance.pending_resolutions}
              alert={d.governance.pending_resolutions > 0}
            />
          </div>
        </div>
      </div>

      {d.fund && (
        <div className="card">
          <h3>Fund (AIF)</h3>
          <div className="row" style={{ gap: 10 }}>
            <Stat label="LPs" value={d.fund.lps} />
            <Stat label="Committed (₹)" value={d.fund.committed} />
            <Stat label="Drawn (₹)" value={d.fund.drawn} />
          </div>
        </div>
      )}
    </div>
  );
}

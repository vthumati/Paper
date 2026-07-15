import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type Dashboard as DashboardT } from "../api";

import Donut from "../components/Donut";
import Stat from "../components/Stat";

export default function Dashboard({ entityId }: { entityId: string }) {
  const nav = useNavigate();
  const [d, setD] = useState<DashboardT | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.dashboard(entityId).then(setD).catch((e) => setError(e.message));
  }, [entityId]);

  if (error) return <p className="error">{error}</p>;
  if (!d) return <p className="muted">Loading…</p>;

  const cap = d.capital;
  const val = d.valuation;
  const poolFree = Math.max(0, cap.esop_pool - cap.esop_granted);
  const usage =
    cap.authorized_shares !== null
      ? [
          { label: "Shares issued", value: cap.issued, color: "#2f6b52" },
          { label: "Options granted", value: cap.esop_granted, color: "#c9a227" },
          { label: "Pool remaining", value: poolFree, color: "#e6d795" },
          { label: "Unissued (authorized)", value: cap.available ?? 0, color: "#d3ddd0" },
        ].filter((s) => s.value > 0)
      : [
          { label: "Shares issued", value: cap.issued, color: "#2f6b52" },
          { label: "Options granted", value: cap.esop_granted, color: "#c9a227" },
          { label: "Pool remaining", value: poolFree, color: "#e6d795" },
        ].filter((s) => s.value > 0);

  return (
    <div>
      <div className="card">
        <h2>Overview</h2>
        <div className="row" style={{ gap: 24, alignItems: "flex-start" }}>
          <div style={{ flex: 1.2, minWidth: 260 }}>
            <label>Class ownership</label>
            <Donut
              segments={d.cap_table.by_class.map((c) => ({ label: c.name, value: c.quantity }))}
              centerValue={d.cap_table.total_shares.toLocaleString()}
              centerLabel="shares issued"
            />
          </div>
          <div style={{ flex: 1.2, minWidth: 260 }}>
            <label>Share usage</label>
            <Donut
              segments={usage}
              centerValue={
                cap.authorized_shares !== null
                  ? cap.authorized_shares.toLocaleString()
                  : (cap.issued + cap.esop_pool).toLocaleString()
              }
              centerLabel={cap.authorized_shares !== null ? "authorized" : "issued + pool"}
            />
          </div>
          <div style={{ minWidth: 190 }}>
            <label>General details</label>
            {cap.authorized_shares !== null && (
              <>
                <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>Authorized shares</div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{cap.authorized_shares.toLocaleString()}</div>
              </>
            )}
            <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>Shares issued</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{cap.issued.toLocaleString()}</div>
            {cap.available !== null && (
              <>
                <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>Available to issue</div>
                <div style={{ fontSize: 18, fontWeight: 700 }}>{cap.available.toLocaleString()}</div>
              </>
            )}
            <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>Capital raised (₹)</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{d.cap_table.total_invested}</div>
            <div className="muted" style={{ marginTop: 8, fontSize: 12 }}>Stakeholders</div>
            <div style={{ fontSize: 18, fontWeight: 700 }}>{d.cap_table.holders}</div>
          </div>
        </div>
      </div>

      <div className="row" style={{ gap: 10 }}>
        <div className="card" style={{ flex: 1.4 }}>
          <h3>Valuation</h3>
          {val.status === "active" ? (
            <>
              <span className="badge complete">Active</span>{" "}
              <strong>FMV ₹{val.fmv_per_share} per share</strong>
              <p className="muted" style={{ marginTop: 6 }}>
                {val.method} · effective {val.valuation_date}
                {val.valid_until ? `, valid until ${val.valid_until}` : ""}
                {val.valuer_name ? ` · ${val.valuer_name}` : ""}
              </p>
            </>
          ) : (
            <>
              <span className="badge danger">Action needed</span>{" "}
              <strong>{val.status === "expired" ? "Valuation expired" : "No valuation on file"}</strong>
              <p className="muted" style={{ marginTop: 6 }}>
                Fix an FMV to price ESOP grants, exercises and new rounds.
              </p>
            </>
          )}
          <button className="secondary" onClick={() => nav("?tab=valuations")}>
            {val.status === "active" ? "View valuations" : "Record a valuation"}
          </button>
        </div>
        <div className="card" style={{ flex: 2 }}>
          <h3>Quick actions</h3>
          <div className="qa-row">
            <button onClick={() => nav("?tab=captable")}>Issue shares</button>
            <button onClick={() => nav("?tab=esop")}>Grant options</button>
            <button onClick={() => nav("?tab=fundraising")}>Raise / issue a SAFE</button>
            <button onClick={() => nav("?tab=governance")}>Pass a resolution</button>
          </div>
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
        <div className="card" style={{ flex: 1 }}>
          <h3>Records</h3>
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Documents" value={d.documents} />
            <Stat label="Data rooms" value={d.data_rooms} />
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

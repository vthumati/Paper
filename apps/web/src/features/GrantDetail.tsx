import { useEffect, useState } from "react";
import { api, type GrantDetail as GrantDetailT } from "../api";
import StackedBar from "../components/StackedBar";
import LineChart from "../components/LineChart";
import ViewToggle from "../components/ViewToggle";
import { fmtMoney } from "../lib/format";

const TYPE_LABEL: Record<string, string> = { option: "Options", rsu: "RSUs", rsa: "RSAs" };

function Stat({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div style={{ flex: 1, minWidth: 150 }}>
      <div className="muted" style={{ fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 24, fontWeight: 700, color: "var(--heading)" }}>{value}</div>
      <div className="muted" style={{ fontSize: 12 }}>{sub}</div>
    </div>
  );
}

/** Ledgy-style single-grant detail: value framing, a vesting status segment
 * bar, and the vesting timeline with a "today" split. */
export default function GrantDetail({ grantId, onClose }: { grantId: string; onClose: () => void }) {
  const [d, setD] = useState<GrantDetailT | null>(null);
  const [error, setError] = useState("");
  const [showPast, setShowPast] = useState(false);
  const [tlView, setTlView] = useState<"chart" | "timeline">("chart");

  useEffect(() => {
    api.grantDetail(grantId).then(setD).catch((e) => setError(e.message));
  }, [grantId]);

  if (error) return <div className="card"><p className="error">{error}</p></div>;
  if (!d) return <div className="card"><p className="muted">Loading…</p></div>;

  const money = (v: string | null) => fmtMoney(v);
  const past = d.schedule.filter((e) => e.past);
  const upcoming = d.schedule.filter((e) => !e.past);
  const settleWord = d.grant_type === "rsu" ? "settled" : d.grant_type === "rsa" ? "issued" : "exercised";

  return (
    <div className="card" style={{ borderColor: "var(--blue)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <h3 style={{ marginTop: 0 }}>
          {d.entity_name} <span className="sec-chip safe">{TYPE_LABEL[d.grant_type]}</span>{" "}
          <span className="muted" style={{ fontSize: 13 }}>granted {d.grant_date}</span>
        </h3>
        <button className="secondary" onClick={onClose}>Close</button>
      </div>

      <div className="row" style={{ gap: 16, margin: "8px 0 16px" }}>
        <Stat label="Today's value" value={money(d.today_value)} sub={`${d.exercisable.toLocaleString()} vested units`} />
        <Stat label={`Value ${settleWord}`} value={money(d.exercised_value)} sub={`${d.exercised.toLocaleString()} ${settleWord} units`} />
        <Stat label="Max potential value" value={money(d.max_potential_value)} sub={`${d.granted.toLocaleString()} units total`} />
      </div>

      {d.tax && (
        <div
          className="card"
          style={{ background: "var(--surface-2, #f6f7f5)", padding: 12, margin: "0 0 16px" }}
        >
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            If you exercised all {d.exercisable.toLocaleString()} vested {settleWord === "exercised" ? "options" : "units"} today
          </div>
          <div className="row" style={{ gap: 16, flexWrap: "wrap" }}>
            <Stat label="Cash to exercise" value={money(d.tax.exercise_cost)} sub={`${d.exercisable.toLocaleString()} × ₹${d.tax.exercise_price}`} />
            <Stat label="Taxable perquisite" value={money(d.tax.perquisite)} sub="FMV − strike" />
            <Stat label="Estimated TDS" value={money(d.tax.tds)} sub={`${(Number(d.tax.marginal_rate) * 100).toFixed(0)}% slab + ${(Number(d.tax.cess_rate) * 100).toFixed(0)}% cess`} />
            <Stat label="Gain after tax" value={money(d.tax.gain_after_tax)} sub="perquisite − TDS" />
          </div>
          <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>
            Estimate only — your actual slab, surcharge and any eligible-startup deferral depend on your total income.
          </div>
        </div>
      )}

      <label>Vesting status</label>
      <StackedBar
        segments={[
          { label: settleWord.charAt(0).toUpperCase() + settleWord.slice(1), value: d.segments.exercised, color: "#1e6b3f" },
          { label: "Vested", value: d.segments.vested, color: "#4caf87" },
          { label: "Unvested", value: d.segments.unvested, color: "#d3ddd0" },
        ].filter((s) => s.value > 0)}
      />

      <label style={{ marginTop: 16, display: "flex", alignItems: "center", gap: 10 }}>
        <span>Vesting timeline</span>
        <span style={{ marginLeft: "auto" }}>
          <ViewToggle
            value={tlView}
            onChange={setTlView}
            options={[
              { value: "chart", label: "Curve" },
              { value: "timeline", label: "Timeline" },
            ]}
          />
        </span>
      </label>
      {tlView === "chart" ? (
        <div>
          <div className="muted" style={{ fontSize: 12, marginBottom: 6 }}>
            Cumulative units vested — the flat stretch is the cliff, then it ramps to the full
            {" "}{d.granted.toLocaleString()} by {d.full_vest_date}. {d.vesting_pct}% vested today.
          </div>
          <LineChart
            height={200}
            yPrefix=""
            series={[
              {
                label: "Units vested",
                color: "#0f9d6b",
                points: [
                  { x: d.grant_date, y: 0 },
                  ...d.schedule.map((e) => ({ x: e.date, y: e.cumulative })),
                ],
              },
            ]}
          />
        </div>
      ) : (
      <>
      <div className="timeline-row">
        <span className="tl-date">{d.grant_date}</span>
        <span>Vesting start</span>
      </div>
      {past.length > 0 && (
        <>
          <div
            className="timeline-row"
            style={{ cursor: "pointer" }}
            onClick={() => setShowPast((v) => !v)}
          >
            <span className="tl-date">past</span>
            <span>
              <strong>{past.length} vesting events</strong> ·{" "}
              {past[past.length - 1].cumulative.toLocaleString()} units vested {showPast ? "▲" : "▾"}
            </span>
          </div>
          {showPast &&
            past.map((e, i) => (
              <div className="timeline-row" key={i} style={{ paddingLeft: 24 }}>
                <span className="tl-date">{e.date}</span>
                <span className="muted">+{e.units.toLocaleString()} units → {e.cumulative.toLocaleString()}</span>
              </div>
            ))}
        </>
      )}
      <div className="timeline-row" style={{ fontWeight: 700, color: "var(--blue)" }}>
        <span className="tl-date">today</span>
        <span>{d.vesting_pct}% vested ({d.vested.toLocaleString()} of {d.granted.toLocaleString()})</span>
      </div>
      {upcoming.slice(0, 6).map((e, i) => (
        <div className="timeline-row" key={i}>
          <span className="tl-date">{e.date}</span>
          <span className="muted">+{e.units.toLocaleString()} units → {e.cumulative.toLocaleString()}</span>
        </div>
      ))}
      {upcoming.length > 6 && (
        <div className="timeline-row">
          <span className="tl-date" />
          <span className="muted">+{upcoming.length - 6} more upcoming events…</span>
        </div>
      )}
      <div className="timeline-row">
        <span className="tl-date">{d.full_vest_date}</span>
        <span>Fully vested</span>
      </div>
      </>
      )}

      {d.documents.length > 0 && (
        <>
          <label style={{ marginTop: 16, display: "block" }}>Documents</label>
          {d.documents.map((doc) => (
            <div className="timeline-row" key={doc.id}>
              <span className="tl-date">{doc.kind === "certificate" ? "certificate" : "letter"}</span>
              <span>
                <button className="secondary" onClick={() => api.downloadPortalDocPdf(doc.id, doc.title)}>
                  ⬇ {doc.title}
                </button>
              </span>
            </div>
          ))}
        </>
      )}
    </div>
  );
}

import Sparkline from "./Sparkline";

export interface StatDelta {
  label: string; // e.g. "vs last quarter"
  pct: number; // signed % change
}

export default function Stat({
  label,
  value,
  big,
  alert,
  hint,
  icon,
  spark,
  deltas,
}: {
  label: string;
  value: string | number;
  big?: boolean;
  alert?: boolean;
  hint?: string;
  icon?: string;
  /** optional trend line rendered under the value (Vestberry-style) */
  spark?: number[];
  /** optional change pills under the value (Visible-style, e.g. QoQ + YoY) */
  deltas?: StatDelta[];
}) {
  return (
    <div className="stat-tile" style={{ flex: "1 1 150px" }}>
      {icon && <div className="stat-icon">{icon}</div>}
      <div
        className="stat-value"
        style={{
          fontSize: big ? 30 : 23,
          color: alert ? "var(--warn)" : "var(--heading)",
        }}
      >
        {value}
      </div>
      {spark && spark.length > 1 && <Sparkline points={spark} />}
      {deltas && deltas.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 2, marginTop: 2 }}>
          {deltas.map((d) => (
            <span key={d.label} style={{ fontSize: 11, whiteSpace: "nowrap" }}>
              <span className={d.pct >= 0 ? "delta-up" : "delta-down"}>
                {d.pct >= 0 ? "▲" : "▼"} {Math.abs(d.pct)}%
              </span>{" "}
              <span className="muted">{d.label}</span>
            </span>
          ))}
        </div>
      )}
      <div className="stat-label">
        {label}
        {hint && (
          <span className="stat-hint" title={hint} aria-label={hint}>
            ⓘ
          </span>
        )}
      </div>
    </div>
  );
}

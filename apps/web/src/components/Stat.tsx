import Sparkline from "./Sparkline";

export default function Stat({
  label,
  value,
  big,
  alert,
  hint,
  icon,
  spark,
}: {
  label: string;
  value: string | number;
  big?: boolean;
  alert?: boolean;
  hint?: string;
  icon?: string;
  /** optional trend line rendered under the value (Vestberry-style) */
  spark?: number[];
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

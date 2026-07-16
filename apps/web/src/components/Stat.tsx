export default function Stat({
  label,
  value,
  big,
  alert,
  hint,
  icon,
}: {
  label: string;
  value: string | number;
  big?: boolean;
  alert?: boolean;
  hint?: string;
  icon?: string;
}) {
  return (
    <div
      className="card"
      style={{ flex: "1 1 150px", margin: 0, textAlign: "center", padding: "14px 10px" }}
    >
      {icon && <div style={{ fontSize: 18, opacity: 0.8, marginBottom: 2 }}>{icon}</div>}
      <div style={{ fontSize: big ? 30 : 22, fontWeight: 700, color: alert ? "var(--warn)" : "var(--navy)" }}>
        {value}
      </div>
      <div className="muted">
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

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

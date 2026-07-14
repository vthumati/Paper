export default function Stat({
  label,
  value,
  big,
  alert,
}: {
  label: string;
  value: string | number;
  big?: boolean;
  alert?: boolean;
}) {
  return (
    <div
      className="card"
      style={{ flex: "1 1 150px", margin: 0, textAlign: "center", padding: "14px 10px" }}
    >
      <div style={{ fontSize: big ? 30 : 22, fontWeight: 700, color: alert ? "var(--warn)" : "var(--navy)" }}>
        {value}
      </div>
      <div className="muted">{label}</div>
    </div>
  );
}

/** Circular gauge for a score or percentage (0–100). Colour bands: red < 40,
 * amber < 70, green ≥ 70 — or pass an explicit colour. */
export default function ProgressRing({
  value,
  label,
  size = 110,
  color,
  suffix = "%",
}: {
  value: number;
  label?: string;
  size?: number;
  color?: string;
  suffix?: string;
}) {
  const pct = Math.max(0, Math.min(100, value));
  const stroke = 10;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const auto = pct < 40 ? "#dc2626" : pct < 70 ? "#f0b429" : "#0f9d6b";
  const col = color ?? auto;
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
      <svg width={size} height={size} role="img" aria-label={`${value}${suffix}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--light)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={col}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${(pct / 100) * c} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
        <text
          x="50%"
          y="50%"
          textAnchor="middle"
          dominantBaseline="central"
          style={{ fontSize: size * 0.24, fontWeight: 700, fill: "var(--heading)" }}
        >
          {Math.round(value)}
          <tspan style={{ fontSize: size * 0.13 }}>{suffix}</tspan>
        </text>
      </svg>
      {label && <div className="muted" style={{ fontSize: 12, textAlign: "center" }}>{label}</div>}
    </div>
  );
}

export interface DonutSegment {
  label: string;
  value: number;
  color?: string;
}

/** Warm-theme palette for chart segments, strongest first. */
export const CHART_COLORS = [
  "#2f6b52",
  "#c9a227",
  "#7fa88f",
  "#8a6d3b",
  "#4a7a63",
  "#b5651d",
  "#94a3b8",
  "#d3ddd0",
];

/** Dependency-free SVG donut chart with a legend (Eqvista-style overview
 * charts). Segments under 0.5% still get a sliver so they stay visible. */
export default function Donut({
  segments,
  size = 150,
  centerValue,
  centerLabel,
}: {
  segments: DonutSegment[];
  size?: number;
  centerValue?: string;
  centerLabel?: string;
}) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  if (total <= 0) return <p className="muted">Nothing to chart yet.</p>;

  const stroke = 26;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
      <svg width={size} height={size} role="img">
        <g transform={`rotate(-90 ${size / 2} ${size / 2})`}>
          {segments.map((s, i) => {
            const frac = s.value / total;
            const dash = Math.max(frac * c - 1.5, 0.5); // 1.5px gap between arcs
            const el = (
              <circle
                key={i}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color ?? CHART_COLORS[i % CHART_COLORS.length]}
                strokeWidth={stroke}
                strokeDasharray={`${dash} ${c - dash}`}
                strokeDashoffset={-offset * c}
              />
            );
            offset += frac;
            return el;
          })}
        </g>
        {centerValue && (
          <text
            x="50%"
            y={centerLabel ? "47%" : "50%"}
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 17, fontWeight: 700, fill: "var(--heading)" }}
          >
            {centerValue}
          </text>
        )}
        {centerLabel && (
          <text
            x="50%"
            y="59%"
            textAnchor="middle"
            dominantBaseline="central"
            style={{ fontSize: 10, fill: "var(--muted, #6b7280)" }}
          >
            {centerLabel}
          </text>
        )}
      </svg>
      <div style={{ fontSize: 13 }}>
        {segments.map((s, i) => (
          <div key={i} style={{ display: "flex", alignItems: "center", gap: 6, padding: "2px 0" }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 3,
                background: s.color ?? CHART_COLORS[i % CHART_COLORS.length],
                flexShrink: 0,
              }}
            />
            <span>{s.label}</span>
            <span className="muted">{((s.value / total) * 100).toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export interface LineSeries {
  label: string;
  color: string;
  points: { x: string; y: number }[]; // x = ISO date label
}

/** Dependency-free SVG line chart with a shared date axis. Series may have
 * different x-values; the axis is the union, positioned by date order. */
export default function LineChart({
  series,
  height = 200,
  yPrefix = "₹",
}: {
  series: LineSeries[];
  height?: number;
  yPrefix?: string;
}) {
  const allX = [...new Set(series.flatMap((s) => s.points.map((p) => p.x)))].sort();
  const allY = series.flatMap((s) => s.points.map((p) => p.y));
  if (allX.length === 0 || allY.length === 0)
    return <p className="muted">No valuation history to chart yet.</p>;

  const W = 640;
  const H = height;
  const padL = 56;
  const padR = 12;
  const padT = 12;
  const padB = 28;
  const maxY = Math.max(...allY);
  const minY = Math.min(0, ...allY);
  const spanY = maxY - minY || 1;

  const xAt = (x: string) => {
    const i = allX.indexOf(x);
    return allX.length === 1
      ? padL + (W - padL - padR) / 2
      : padL + (i / (allX.length - 1)) * (W - padL - padR);
  };
  const yAt = (y: number) => padT + (1 - (y - minY) / spanY) * (H - padT - padB);

  const ticks = [minY, minY + spanY / 2, maxY];
  const fmt = (v: number) =>
    v >= 1e7 ? `${(v / 1e7).toFixed(1)}Cr` : v >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : `${Math.round(v)}`;

  return (
    <div style={{ overflowX: "auto" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" style={{ maxWidth: W }}>
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={padL} y1={yAt(t)} x2={W - padR} y2={yAt(t)} stroke="var(--border)" strokeWidth="1" />
            <text x={padL - 6} y={yAt(t) + 3} textAnchor="end" style={{ fontSize: 10, fill: "var(--muted, #6b7280)" }}>
              {yPrefix}{fmt(t)}
            </text>
          </g>
        ))}
        {allX.map((x) => (
          <text
            key={x}
            x={xAt(x)}
            y={H - 8}
            textAnchor="middle"
            style={{ fontSize: 9, fill: "var(--muted, #6b7280)" }}
          >
            {x.slice(0, 7)}
          </text>
        ))}
        {series.map((s) => {
          const pts = [...s.points].sort((a, b) => a.x.localeCompare(b.x));
          if (pts.length === 0) return null;
          const d = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${xAt(p.x)} ${yAt(p.y)}`).join(" ");
          return (
            <g key={s.label}>
              {pts.length > 1 && <path d={d} fill="none" stroke={s.color} strokeWidth="2" />}
              {pts.map((p, i) => (
                <circle key={i} cx={xAt(p.x)} cy={yAt(p.y)} r="3" fill={s.color} />
              ))}
            </g>
          );
        })}
      </svg>
      <div style={{ display: "flex", gap: 16, fontSize: 12, marginTop: 4 }}>
        {series.map((s) => (
          <span key={s.label} style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 12, height: 3, background: s.color, display: "inline-block" }} />
            {s.label}
          </span>
        ))}
      </div>
    </div>
  );
}

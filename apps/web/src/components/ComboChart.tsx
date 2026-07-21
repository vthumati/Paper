/** Dependency-free SVG combo chart (Visible-style "Revenue & Change %"):
 * bars on a left value axis plus an optional line on a right % axis,
 * sharing one category axis. */
export default function ComboChart({
  categories,
  bars,
  line,
  barLabel,
  lineLabel,
  height = 200,
  yPrefix = "₹",
}: {
  categories: string[]; // shared x labels, in order
  bars: (number | null)[]; // aligned to categories
  line?: (number | null)[]; // aligned to categories, right axis (%)
  barLabel: string;
  lineLabel?: string;
  height?: number;
  yPrefix?: string;
}) {
  const barVals = bars.filter((v): v is number => v !== null);
  if (categories.length === 0 || barVals.length === 0)
    return <p className="muted">Not enough history to chart yet.</p>;

  const W = 640;
  const H = height;
  const padL = 56;
  const padR = 44;
  const padT = 12;
  const padB = 28;
  const plotW = W - padL - padR;
  const plotH = H - padT - padB;

  const maxBar = Math.max(...barVals, 1);
  const lineVals = (line ?? []).filter((v): v is number => v !== null);
  const maxLine = Math.max(...lineVals, 0);
  const minLine = Math.min(...lineVals, 0);
  const spanLine = maxLine - minLine || 1;

  const slot = plotW / categories.length;
  const barW = Math.min(34, slot * 0.55);
  const xMid = (i: number) => padL + slot * i + slot / 2;
  const yBar = (v: number) => padT + (1 - v / maxBar) * plotH;
  const yLine = (v: number) => padT + (1 - (v - minLine) / spanLine) * plotH;

  const fmt = (v: number) =>
    v >= 1e7 ? `${(v / 1e7).toFixed(1)}Cr` : v >= 1e5 ? `${(v / 1e5).toFixed(1)}L` : `${Math.round(v)}`;

  const linePts = (line ?? [])
    .map((v, i) => (v === null ? null : { i, v }))
    .filter((p): p is { i: number; v: number } => p !== null);

  return (
    <div style={{ overflowX: "auto" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" role="img" style={{ maxWidth: W }}>
        {[0, maxBar / 2, maxBar].map((t, i) => (
          <g key={i}>
            <line x1={padL} y1={yBar(t)} x2={W - padR} y2={yBar(t)} stroke="var(--border)" strokeWidth="1" />
            <text x={padL - 6} y={yBar(t) + 3} textAnchor="end" style={{ fontSize: 10, fill: "var(--muted, #6b7280)" }}>
              {yPrefix}{fmt(t)}
            </text>
          </g>
        ))}
        {line && lineVals.length > 0 && (
          <>
            <text x={W - padR + 6} y={yLine(maxLine) + 3} style={{ fontSize: 10, fill: "var(--muted, #6b7280)" }}>
              {Math.round(maxLine)}%
            </text>
            <text x={W - padR + 6} y={yLine(minLine) + 3} style={{ fontSize: 10, fill: "var(--muted, #6b7280)" }}>
              {Math.round(minLine)}%
            </text>
          </>
        )}
        {categories.map((c, i) => (
          <text key={c + i} x={xMid(i)} y={H - 8} textAnchor="middle" style={{ fontSize: 9, fill: "var(--muted, #6b7280)" }}>
            {c}
          </text>
        ))}
        {bars.map((v, i) =>
          v === null ? null : (
            <rect
              key={i}
              x={xMid(i) - barW / 2}
              y={yBar(v)}
              width={barW}
              height={Math.max(1, padT + plotH - yBar(v))}
              rx="3"
              fill="var(--blue, #2f6fb2)"
              opacity="0.85"
            >
              <title>{`${categories[i]}: ${yPrefix}${fmt(v)}`}</title>
            </rect>
          )
        )}
        {linePts.length > 0 && (
          <g>
            {linePts.length > 1 && (
              <path
                d={linePts.map((p, k) => `${k === 0 ? "M" : "L"} ${xMid(p.i)} ${yLine(p.v)}`).join(" ")}
                fill="none"
                stroke="var(--green, #1e6b3f)"
                strokeWidth="2"
              />
            )}
            {linePts.map((p) => (
              <circle key={p.i} cx={xMid(p.i)} cy={yLine(p.v)} r="3" fill="var(--green, #1e6b3f)">
                <title>{`${categories[p.i]}: ${Math.round(p.v * 10) / 10}%`}</title>
              </circle>
            ))}
          </g>
        )}
      </svg>
      <div style={{ display: "flex", gap: 16, fontSize: 12, marginTop: 4 }}>
        <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
          <span style={{ width: 12, height: 8, background: "var(--blue, #2f6fb2)", display: "inline-block", borderRadius: 2 }} />
          {barLabel}
        </span>
        {lineLabel && linePts.length > 0 && (
          <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 12, height: 3, background: "var(--green, #1e6b3f)", display: "inline-block" }} />
            {lineLabel}
          </span>
        )}
      </div>
    </div>
  );
}

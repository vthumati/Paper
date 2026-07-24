import { CHART_COLORS } from "./Donut";

export interface TreemapItem {
  label: string;
  value: number; // sizes the rectangle
  color?: string;
  hint?: string;
}

interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** Recursive binary-split layout: sorted items are halved by cumulative value
 * and the rectangle is split along its longer axis, giving reasonable aspect
 * ratios without a full squarified implementation. */
function split(items: { i: number; value: number }[], r: Rect): { i: number; rect: Rect }[] {
  if (items.length === 0) return [];
  if (items.length === 1) return [{ i: items[0].i, rect: r }];
  const total = items.reduce((s, x) => s + x.value, 0);
  let acc = 0;
  let cut = 1;
  for (let k = 0; k < items.length; k++) {
    acc += items[k].value;
    cut = k + 1;
    if (acc >= total / 2) break;
  }
  const a = items.slice(0, cut);
  const b = items.slice(cut);
  const frac = a.reduce((s, x) => s + x.value, 0) / total;
  const [ra, rb]: [Rect, Rect] =
    r.w >= r.h
      ? [{ ...r, w: r.w * frac }, { x: r.x + r.w * frac, y: r.y, w: r.w * (1 - frac), h: r.h }]
      : [{ ...r, h: r.h * frac }, { x: r.x, y: r.y + r.h * frac, w: r.w, h: r.h * (1 - frac) }];
  return [...split(a, ra), ...split(b, rb)];
}

/** Dependency-free SVG treemap: rectangle area ∝ value. Colour is caller-driven
 * (e.g. by MOIC) so the map doubles as a heat view. */
export default function Treemap({
  items,
  width = 720,
  height = 280,
  format = (v: number) => String(v),
}: {
  items: TreemapItem[];
  width?: number;
  height?: number;
  format?: (v: number) => string;
}) {
  const live = items.map((it, i) => ({ ...it, i })).filter((x) => x.value > 0);
  if (live.length === 0) return <p className="muted">Nothing to chart yet.</p>;
  live.sort((a, b) => b.value - a.value);
  const placed = split(
    live.map((x) => ({ i: x.i, value: x.value })),
    { x: 0, y: 0, w: width, h: height }
  );

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" style={{ maxWidth: width }}>
      {placed.map((p) => {
        const it = live.find((x) => x.i === p.i)!;
        const { x, y, w, h } = p.rect;
        const color = it.color ?? CHART_COLORS[p.i % CHART_COLORS.length];
        const showLabel = w > 54 && h > 24;
        return (
          <g key={p.i}>
            <rect
              x={x + 1}
              y={y + 1}
              width={Math.max(w - 2, 0)}
              height={Math.max(h - 2, 0)}
              rx={4}
              fill={color}
              fillOpacity={0.88}
            >
              <title>{it.hint ?? `${it.label}: ${format(it.value)}`}</title>
            </rect>
            {showLabel && (
              <text x={x + 8} y={y + 18} style={{ fontSize: 11, fontWeight: 600, fill: "#04160f" }}>
                {it.label}
              </text>
            )}
            {showLabel && h > 40 && (
              <text x={x + 8} y={y + 32} style={{ fontSize: 10, fill: "#04160f", opacity: 0.72 }}>
                {format(it.value)}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

import { CHART_COLORS } from "./Donut";

export interface SankeyNode {
  id: string;
  label: string;
  color?: string;
}
export interface SankeyLink {
  source: string;
  target: string;
  value: number;
}

/** Dependency-free SVG Sankey / flow diagram. Nodes are auto-arranged into
 * columns by longest path from a root; link ribbons are sized to their value.
 * Used to show how capital moves (committed → drawn → deployed → holdings).
 * Values must conserve reasonably for the ribbons to read cleanly. */
export default function Sankey({
  nodes,
  links,
  height = 260,
  width = 760,
  format = (v: number) => String(Math.round(v)),
}: {
  nodes: SankeyNode[];
  links: SankeyLink[];
  height?: number;
  width?: number;
  format?: (v: number) => string;
}) {
  const live = links.filter((l) => l.value > 0);
  if (nodes.length === 0 || live.length === 0)
    return <p className="muted">Not enough data to chart the flow yet.</p>;

  const byId = new Map(nodes.map((n, i) => [n.id, { ...n, i }]));
  const inSum = new Map<string, number>();
  const outSum = new Map<string, number>();
  for (const l of live) {
    outSum.set(l.source, (outSum.get(l.source) ?? 0) + l.value);
    inSum.set(l.target, (inSum.get(l.target) ?? 0) + l.value);
  }
  const nodeVal = (id: string) => Math.max(inSum.get(id) ?? 0, outSum.get(id) ?? 0);

  // column = longest path from any root (node with no incoming link)
  const col = new Map<string, number>();
  const targets = new Set(live.map((l) => l.target));
  for (const n of nodes) if (!targets.has(n.id)) col.set(n.id, 0);
  // relax edges until stable (DAG, so bounded by node count)
  for (let pass = 0; pass < nodes.length; pass++) {
    let changed = false;
    for (const l of live) {
      const c = (col.get(l.source) ?? 0) + 1;
      if (c > (col.get(l.target) ?? 0)) {
        col.set(l.target, c);
        changed = true;
      }
    }
    if (!changed) break;
  }
  const maxCol = Math.max(0, ...[...col.values()]);

  // group nodes per column, keeping declared order
  const cols: string[][] = Array.from({ length: maxCol + 1 }, () => []);
  for (const n of nodes) if (nodeVal(n.id) > 0) cols[col.get(n.id) ?? 0].push(n.id);

  const pad = 8;
  const gap = 16; // vertical gap between nodes in a column
  const nodeW = 13;
  // global vertical scale so ribbon widths match across columns
  let scale = Infinity;
  cols.forEach((ids) => {
    const total = ids.reduce((s, id) => s + nodeVal(id), 0);
    if (total <= 0) return;
    const avail = height - 2 * pad - (ids.length - 1) * gap;
    scale = Math.min(scale, avail / total);
  });
  if (!isFinite(scale) || scale <= 0) scale = 1;

  // lay out node rects
  type Rect = { id: string; x: number; y0: number; y1: number; color: string; c: number };
  const rects = new Map<string, Rect>();
  const colX = (c: number) =>
    maxCol === 0 ? pad : pad + (c * (width - 2 * pad - nodeW)) / maxCol;
  cols.forEach((ids, c) => {
    const total = ids.reduce((s, id) => s + nodeVal(id), 0);
    const stackH = total * scale + (ids.length - 1) * gap;
    let y = pad + (height - 2 * pad - stackH) / 2;
    ids.forEach((id) => {
      const h = Math.max(nodeVal(id) * scale, 1);
      const node = byId.get(id)!;
      rects.set(id, {
        id,
        x: colX(c),
        y0: y,
        y1: y + h,
        color: node.color ?? CHART_COLORS[node.i % CHART_COLORS.length],
        c,
      });
      y += h + gap;
    });
  });

  // ribbons, stacked in order on each node's edge
  const outOff = new Map<string, number>();
  const inOff = new Map<string, number>();
  const ribbons = live
    .map((l, i) => {
      const s = rects.get(l.source);
      const t = rects.get(l.target);
      if (!s || !t) return null;
      const w = l.value * scale;
      const sy = s.y0 + (outOff.get(l.source) ?? 0);
      const ty = t.y0 + (inOff.get(l.target) ?? 0);
      outOff.set(l.source, (outOff.get(l.source) ?? 0) + w);
      inOff.set(l.target, (inOff.get(l.target) ?? 0) + w);
      const x0 = s.x + nodeW;
      const x1 = t.x;
      const mx = (x0 + x1) / 2;
      const d = `M${x0},${sy} C${mx},${sy} ${mx},${ty} ${x1},${ty} L${x1},${ty + w} C${mx},${ty + w} ${mx},${sy + w} ${x0},${sy + w} Z`;
      return (
        <path key={i} d={d} fill={s.color} fillOpacity={0.32}>
          <title>{`${byId.get(l.source)?.label} → ${byId.get(l.target)?.label}: ${format(l.value)}`}</title>
        </path>
      );
    })
    .filter(Boolean);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" style={{ maxWidth: width }}>
      {ribbons}
      {[...rects.values()].map((r) => {
        const labelLeft = r.c === maxCol && maxCol > 0;
        return (
          <g key={r.id}>
            <rect x={r.x} y={r.y0} width={nodeW} height={Math.max(r.y1 - r.y0, 1)} rx={2} fill={r.color}>
              <title>{`${byId.get(r.id)?.label}: ${format(nodeVal(r.id))}`}</title>
            </rect>
            <text
              x={labelLeft ? r.x - 6 : r.x + nodeW + 6}
              y={(r.y0 + r.y1) / 2}
              textAnchor={labelLeft ? "end" : "start"}
              dominantBaseline="central"
              style={{ fontSize: 11, fill: "var(--heading)" }}
            >
              {byId.get(r.id)?.label}
              <tspan style={{ fill: "var(--muted, #6b7280)" }}> {format(nodeVal(r.id))}</tspan>
            </text>
          </g>
        );
      })}
    </svg>
  );
}

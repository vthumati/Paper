import { CHART_COLORS } from "./Donut";

export interface Column {
  label: string;
  /** stacked segments, bottom-up; values in the same unit */
  segments: { label: string; value: number; color?: string }[];
}

/** Vertical stacked columns (Vestberry waterfall-analysis style) — CSS-only,
 * columns scaled to the tallest total, shared legend from segment labels. */
export default function ColumnChart({
  columns,
  height = 180,
  format = (v: number) => String(v),
}: {
  columns: Column[];
  height?: number;
  format?: (v: number) => string;
}) {
  const totals = columns.map((c) => c.segments.reduce((s, x) => s + x.value, 0));
  const max = Math.max(...totals, 1);
  const legend = columns[0]?.segments.map((s) => s.label) ?? [];
  const colorFor = (label: string, i: number) =>
    columns[0]?.segments[i]?.color ?? CHART_COLORS[i % CHART_COLORS.length];

  return (
    <div>
      <div style={{ display: "flex", alignItems: "flex-end", gap: 18, height }}>
        {columns.map((c, ci) => (
          <div key={c.label} style={{ flex: "0 0 72px", display: "flex", flexDirection: "column", alignItems: "center", height: "100%" }}>
            <div
              style={{ display: "flex", flexDirection: "column-reverse", justifyContent: "flex-start", width: 46, height: "100%" }}
              title={`${c.label}: ${format(totals[ci])}`}
            >
              {c.segments.map((s, i) => (
                <div
                  key={s.label}
                  title={`${s.label}: ${format(s.value)}`}
                  style={{
                    height: `${(s.value / max) * 100}%`,
                    background: s.color ?? colorFor(s.label, i),
                    borderRadius: 2,
                    marginTop: 1,
                  }}
                />
              ))}
            </div>
            <div className="muted" style={{ fontSize: 11, marginTop: 4, textAlign: "center" }}>
              {c.label}
              <br />
              {format(totals[ci])}
            </div>
          </div>
        ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginTop: 8 }}>
        {legend.map((l, i) => (
          <span key={l} className="muted" style={{ fontSize: 12, display: "inline-flex", alignItems: "center", gap: 5 }}>
            <span style={{ width: 10, height: 10, borderRadius: 2, background: colorFor(l, i), display: "inline-block" }} />
            {l}
          </span>
        ))}
      </div>
    </div>
  );
}

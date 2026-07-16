import { CHART_COLORS } from "./Donut";

export interface Bar {
  label: string;
  value: number;
  color?: string;
  /** optional pre-formatted value shown at the bar end (defaults to toLocaleString) */
  display?: string;
}

/** Horizontal bar chart — a legible alternative to a dense number table for
 * waterfalls, payouts and dilution. Bars are scaled to the largest value. */
export default function BarChart({
  bars,
  height = 22,
  prefix = "",
}: {
  bars: Bar[];
  height?: number;
  prefix?: string;
}) {
  const max = Math.max(...bars.map((b) => Math.abs(b.value)), 1);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      {bars.map((b, i) => (
        <div key={i} style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{ width: 130, fontSize: 13, textAlign: "right", flexShrink: 0 }}>{b.label}</div>
          <div style={{ flex: 1, background: "var(--light)", borderRadius: 6, overflow: "hidden" }}>
            <div
              style={{
                width: `${(Math.abs(b.value) / max) * 100}%`,
                minWidth: b.value ? 2 : 0,
                height,
                background: b.color ?? CHART_COLORS[i % CHART_COLORS.length],
                borderRadius: 6,
              }}
            />
          </div>
          <div style={{ width: 110, fontSize: 13, fontWeight: 600, flexShrink: 0 }}>
            {b.display ?? `${prefix}${b.value.toLocaleString("en-IN")}`}
          </div>
        </div>
      ))}
    </div>
  );
}

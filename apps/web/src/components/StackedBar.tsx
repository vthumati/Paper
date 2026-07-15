import { CHART_COLORS } from "./Donut";

export interface BarSegment {
  label: string;
  value: number;
  color?: string;
}

/** 100%-stacked horizontal ownership bar (Mantle-style): a single slim bar
 * segmented by share class with an inline legend of % labels. Complements the
 * donut with a compact left-to-right read. */
export default function StackedBar({ segments }: { segments: BarSegment[] }) {
  const total = segments.reduce((s, x) => s + x.value, 0);
  if (total <= 0) return null;
  return (
    <div>
      <div
        style={{
          display: "flex",
          height: 22,
          borderRadius: 6,
          overflow: "hidden",
          border: "1px solid var(--border)",
        }}
      >
        {segments.map((s, i) => (
          <div
            key={i}
            title={`${s.label} — ${((s.value / total) * 100).toFixed(2)}%`}
            style={{
              width: `${(s.value / total) * 100}%`,
              background: s.color ?? CHART_COLORS[i % CHART_COLORS.length],
            }}
          />
        ))}
      </div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 8, fontSize: 12 }}>
        {segments.map((s, i) => (
          <span key={i} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span
              style={{
                width: 10,
                height: 10,
                borderRadius: 3,
                background: s.color ?? CHART_COLORS[i % CHART_COLORS.length],
                flexShrink: 0,
              }}
            />
            {s.label} <strong>{((s.value / total) * 100).toFixed(2)}%</strong>
          </span>
        ))}
      </div>
    </div>
  );
}

export type HeatTone = "ok" | "warn" | "bad";
export interface HeatItem {
  date: string; // ISO date
  tone: HeatTone;
  label?: string;
}

const TONE: Record<HeatTone, { bg: string; bd: string; fg: string }> = {
  ok: { bg: "rgba(15,157,107,0.16)", bd: "rgba(15,157,107,0.55)", fg: "#0f9d6b" },
  warn: { bg: "rgba(208,152,42,0.18)", bd: "rgba(208,152,42,0.6)", fg: "#a9791b" },
  bad: { bg: "rgba(192,85,47,0.18)", bd: "rgba(192,85,47,0.6)", fg: "#c0552f" },
};
const RANK: Record<HeatTone, number> = { ok: 0, warn: 1, bad: 2 };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** Month-bucketed heatmap: each cell is a calendar month between the earliest
 * and latest dated item, tinted by the most urgent tone due that month with a
 * count badge. A compact "when is everything due" read over a wall of rows. */
export default function CalendarHeatmap({ items }: { items: HeatItem[] }) {
  const dated = items.filter((i) => /^\d{4}-\d{2}/.test(i.date));
  if (dated.length === 0) return <p className="muted">Nothing with a due date to chart yet.</p>;

  const keys = dated.map((i) => i.date.slice(0, 7)).sort();
  const [minY, minM] = keys[0].split("-").map(Number);
  const [maxY, maxM] = keys[keys.length - 1].split("-").map(Number);
  const months: string[] = [];
  for (let y = minY, m = minM; y < maxY || (y === maxY && m <= maxM); ) {
    months.push(`${y}-${String(m).padStart(2, "0")}`);
    if (months.length > 36) break; // safety cap
    m += 1;
    if (m > 12) { m = 1; y += 1; }
  }

  const byMonth = new Map<string, HeatItem[]>();
  for (const it of dated) {
    const k = it.date.slice(0, 7);
    (byMonth.get(k) ?? byMonth.set(k, []).get(k)!).push(it);
  }

  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
      {months.map((k) => {
        const its = byMonth.get(k) ?? [];
        const worst = its.reduce<HeatTone | null>(
          (w, it) => (w === null || RANK[it.tone] > RANK[w] ? it.tone : w),
          null
        );
        const t = worst ? TONE[worst] : null;
        const [y, m] = k.split("-").map(Number);
        return (
          <div
            key={k}
            title={its.length ? its.map((i) => `${i.date} — ${i.label ?? i.tone}`).join("\n") : "Nothing due"}
            style={{
              flex: "0 0 auto",
              minWidth: 66,
              padding: "8px 10px",
              borderRadius: 10,
              border: `1px solid ${t ? t.bd : "var(--border)"}`,
              background: t ? t.bg : "transparent",
              textAlign: "center",
            }}
          >
            <div style={{ fontSize: 11, color: "var(--muted, #6b7280)" }}>
              {MONTHS[m - 1]} '{String(y).slice(2)}
            </div>
            <div style={{ fontSize: 18, fontWeight: 700, color: t ? t.fg : "var(--border)" }}>
              {its.length || "·"}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/** Number & money formatting — one source of truth, Indian conventions
 * (lakh/crore grouping via the en-IN locale). Use these instead of bare
 * `.toLocaleString()` (whose grouping varies by the viewer's browser locale)
 * or hand-rolled `₹${...}` interpolation. */

export function fmtInt(n: number | string): string {
  const v = typeof n === "string" ? Number(n) : n;
  return Number.isFinite(v) ? v.toLocaleString("en-IN") : String(n);
}

/** Compact relative time, e.g. "just now", "3h ago", "2d ago", "5w ago".
 * Falls back to a date for anything older than ~8 weeks. Blank → "—". */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "—";
  const then = new Date(iso).getTime();
  if (!Number.isFinite(then)) return "—";
  const s = Math.max(0, (Date.now() - then) / 1000);
  if (s < 60) return "just now";
  const m = s / 60;
  if (m < 60) return `${Math.floor(m)}m ago`;
  const h = m / 60;
  if (h < 24) return `${Math.floor(h)}h ago`;
  const d = h / 24;
  if (d < 7) return `${Math.floor(d)}d ago`;
  const w = d / 7;
  if (w < 8) return `${Math.floor(w)}w ago`;
  return new Date(iso).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

/** Rupee amount with lakh/crore grouping and up to 2 decimals. Blank/undefined
 * renders as the placeholder (default "—"). */
export function fmtMoney(
  v: number | string | null | undefined,
  blank = "—"
): string {
  if (v === null || v === undefined || v === "") return blank;
  const n = typeof v === "string" ? Number(v) : v;
  if (!Number.isFinite(n)) return String(v);
  return `₹${n.toLocaleString("en-IN", { maximumFractionDigits: 2 })}`;
}

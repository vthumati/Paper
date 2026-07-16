/** Number & money formatting — one source of truth, Indian conventions
 * (lakh/crore grouping via the en-IN locale). Use these instead of bare
 * `.toLocaleString()` (whose grouping varies by the viewer's browser locale)
 * or hand-rolled `₹${...}` interpolation. */

export function fmtInt(n: number | string): string {
  const v = typeof n === "string" ? Number(n) : n;
  return Number.isFinite(v) ? v.toLocaleString("en-IN") : String(n);
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

const PLACEHOLDER_RE = /\$([a-z][a-z0-9_]*)/g;

export function placeholders(body: string): string[] {
  return [...new Set([...body.matchAll(PLACEHOLDER_RE)].map((m) => m[1]))];
}

/** Substitute filled values; unfilled placeholders render as ‹name› markers. */
export function renderPreview(body: string, values: Record<string, string>): string {
  return body.replace(PLACEHOLDER_RE, (_, k) => values[k]?.trim() || `‹${k}›`);
}

export function missingFields(body: string, values: Record<string, string>): string[] {
  return placeholders(body).filter((f) => !values[f]?.trim());
}

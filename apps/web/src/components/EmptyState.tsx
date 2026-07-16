import type { ReactNode } from "react";

/** Friendly empty state: an icon, a title, a one-line hint and an optional
 * primary action — replaces bare "No X yet." text. */
export default function EmptyState({
  icon = "📭",
  title,
  hint,
  action,
}: {
  icon?: string;
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div
      style={{
        textAlign: "center",
        padding: "32px 16px",
        color: "var(--muted)",
      }}
    >
      <div style={{ fontSize: 34, marginBottom: 8, opacity: 0.85 }}>{icon}</div>
      <div style={{ fontWeight: 600, color: "var(--heading)", marginBottom: 4 }}>{title}</div>
      {hint && <div style={{ fontSize: 13, maxWidth: 420, margin: "0 auto 12px" }}>{hint}</div>}
      {action}
    </div>
  );
}

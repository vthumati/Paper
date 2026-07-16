import type { ReactNode } from "react";

/** Consistent tab header: an icon, title, subtitle and an optional right-side
 * action/stat slot — gives each screen hierarchy instead of opening on a card. */
export default function PageHeader({
  icon,
  title,
  subtitle,
  right,
}: {
  icon?: string;
  title: string;
  subtitle?: string;
  right?: ReactNode;
}) {
  return (
    <div
      style={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: 12,
        margin: "0 0 12px",
        flexWrap: "wrap",
      }}
    >
      <div>
        <h2 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
          {icon && <span style={{ fontSize: 22 }}>{icon}</span>}
          {title}
        </h2>
        {subtitle && <p className="muted" style={{ margin: "2px 0 0" }}>{subtitle}</p>}
      </div>
      {right && <div style={{ display: "flex", alignItems: "center", gap: 8 }}>{right}</div>}
    </div>
  );
}

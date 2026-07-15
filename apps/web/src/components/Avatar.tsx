/** Two-letter initials avatar chip (Mantle-style) for people/entity tables.
 * Deterministic tint per name so the same person reads consistently. */
const TINTS = ["#2f6b52", "#2f4b6b", "#8a6d3b", "#8a5a2b", "#52525b", "#7a6512"];

function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export default function Avatar({ name }: { name: string | null | undefined }) {
  const n = name || "?";
  let h = 0;
  for (let i = 0; i < n.length; i++) h = (h * 31 + n.charCodeAt(i)) % TINTS.length;
  return (
    <span className="avatar" style={{ background: TINTS[h] }} title={n}>
      {initials(n)}
    </span>
  );
}

/** Tinted security-class chip (Eqvista-style): the class kind picks the
 * colour so dense cap-table rows stay scannable. */
export default function SecChip({
  name,
  kind,
}: {
  name: string | null | undefined;
  kind?: string | null;
}) {
  if (!name) return <>—</>;
  return <span className={`sec-chip ${kind ?? "equity"}`}>{name}</span>;
}

/** Compact segmented control for switching a card between a graphical view and
 * the underlying table (chart is the default view). Sits in the card header. */
export default function ViewToggle<T extends string>({
  options,
  value,
  onChange,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
}) {
  return (
    <span className="view-toggle">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          className={o.value === value ? "active" : ""}
          onClick={() => onChange(o.value)}
        >
          {o.label}
        </button>
      ))}
    </span>
  );
}

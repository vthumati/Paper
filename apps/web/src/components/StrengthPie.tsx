/** 4Degrees-style relationship-strength pie (0-100, from logged touches). */
export default function StrengthPie({ value }: { value: number }) {
  return (
    <span
      title={`Relationship strength ${value}/100 — frequency and recency of logged touches`}
      style={{
        display: "inline-block",
        width: 14,
        height: 14,
        borderRadius: "50%",
        background: `conic-gradient(var(--blue) ${value * 3.6}deg, var(--light) 0deg)`,
        border: "1px solid var(--border)",
        verticalAlign: "-2px",
      }}
    />
  );
}

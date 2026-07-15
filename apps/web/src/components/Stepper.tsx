export type StepState = "done" | "active" | "todo";

/** Mini progress stepper: dots + labels, e.g. board → agreement → e-sign. */
export default function Stepper({
  steps,
}: {
  steps: { label: string; state: StepState }[];
}) {
  return (
    <span className="stepper">
      {steps.map((s, i) => (
        <span key={s.label} className={`step ${s.state}`}>
          {i > 0 && <span className="step-line" />}
          <span className="step-dot" />
          <span className="step-label">{s.label}</span>
        </span>
      ))}
    </span>
  );
}

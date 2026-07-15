import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type EntityTasks } from "../api";

const SEV_BADGE: Record<string, string> = { red: "danger", amber: "active", ok: "complete" };
const KIND_LABEL: Record<string, string> = {
  signature: "Signature",
  exercise: "ESOP",
  compliance: "Compliance",
  consent: "Consent",
};

/** App-wide task hub (Mantle-style): everything actionable for the entity in
 * one ranked list, each row deep-linking to the tab that resolves it. */
export default function TasksHub({ entityId }: { entityId: string }) {
  const nav = useNavigate();
  const [data, setData] = useState<EntityTasks | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.entityTasks(entityId).then(setData).catch((e) => setError(e.message));
  }, [entityId]);

  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="muted">Loading…</p>;

  return (
    <div className="card">
      <h2>
        Tasks{" "}
        <span className={`badge ${data.counts.overdue > 0 ? "danger" : ""}`}>
          {data.counts.total} open{data.counts.overdue > 0 ? ` · ${data.counts.overdue} overdue` : ""}
        </span>
      </h2>
      <p className="muted">
        Everything awaiting action across this company — pending e-signatures, option-exercise
        requests, overdue filings and outstanding investor consents.
      </p>
      {data.tasks.length === 0 ? (
        <p className="muted">Nothing needs your attention. 🎉</p>
      ) : (
        data.tasks.map((t, i) => (
          <div
            key={i}
            className="timeline-row"
            style={{ alignItems: "center", justifyContent: "space-between" }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span className={`badge ${SEV_BADGE[t.severity] ?? ""}`}>
                {KIND_LABEL[t.kind] ?? t.kind}
              </span>
              <span>
                <strong>{t.title}</strong>
                <div className="muted" style={{ fontSize: 12 }}>{t.detail}</div>
              </span>
            </span>
            <button className="secondary" onClick={() => nav(`?tab=${t.tab}`)}>
              Resolve →
            </button>
          </div>
        ))
      )}
    </div>
  );
}

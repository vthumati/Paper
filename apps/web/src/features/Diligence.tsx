import { useEffect, useState } from "react";
import { api, type DiligenceResult } from "../api";
import { useGuard } from "../hooks";

const SEV_LABEL: Record<string, string> = { high: "High", medium: "Medium", low: "Low" };

export default function Diligence({
  entityId,
  onNavigate,
}: {
  entityId: string;
  onNavigate: (tab: string) => void;
}) {
  const [d, setD] = useState<DiligenceResult | null>(null);
  const [reportMsg, setReportMsg] = useState("");
  const { error, setError, guard } = useGuard(() => load());

  async function load() {
    try {
      setD(await api.getDiligence(entityId));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  if (!d) return <p className="muted">Running diligence checks…</p>;

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>Diligence readiness</h2>
        <p className="muted">
          {d.checks_run} automated checks over your own records — what an investor's lawyers
          will look for, before they look.
        </p>
        <div className="row" style={{ alignItems: "baseline", gap: 16 }}>
          <span style={{ fontSize: 42, fontWeight: 700 }}>{d.score}</span>
          <span className="muted">/ 100</span>
          <span className="muted">
            {d.counts.high} high · {d.counts.medium} medium · {d.counts.low} low
          </span>
          <button
            className="secondary"
            onClick={guard(async () => {
              const doc = await api.generateDiligenceReport(entityId);
              setReportMsg(`Report saved to Documents: "${doc.title}"`);
            })}
          >
            Save report to Documents
          </button>
        </div>
        {reportMsg && <p className="muted">{reportMsg}</p>}
      </div>

      {d.findings.length === 0 ? (
        <div className="card">
          <p>No findings — the record is diligence-ready. 🎉</p>
        </div>
      ) : (
        <div className="card">
          <h3>Findings</h3>
          {d.findings.map((f) => (
            <div
              key={f.code}
              style={{ borderTop: "1px solid var(--border)", padding: "10px 0" }}
            >
              <span
                className={`badge ${
                  f.severity === "high" ? "danger" : f.severity === "medium" ? "active" : ""
                }`}
              >
                {SEV_LABEL[f.severity]}
              </span>{" "}
              <strong>{f.title}</strong>
              <div className="muted" style={{ margin: "4px 0" }}>{f.detail}</div>
              <button className="secondary" onClick={() => onNavigate(f.tab)}>
                Fix in {f.tab} →
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

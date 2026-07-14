import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import { api, ApiError, type Benefit, type Eligibility, type Recognition } from "../api";

const BENEFIT_LABELS: Record<string, string> = {
  section_80iac: "80-IAC tax holiday",
  angel_tax_56_2_viib: "Angel-tax exemption (56(2)(viib))",
};
const REC_STATUSES = ["not_applied", "applied", "recognised", "rejected"];

export default function StartupIndia({ entityId }: { entityId: string }) {
  const [elig, setElig] = useState<Eligibility | null>(null);
  const [rec, setRec] = useState<Recognition | null>(null);
  const [benefits, setBenefits] = useState<Benefit[]>([]);
  const { error, setError, guard } = useGuard(() => load());

  const [status, setStatus] = useState("recognised");
  const [dpiit, setDpiit] = useState("");

  async function load() {
    try {
      setElig(await api.startupEligibility(entityId));
      try {
        setRec(await api.getRecognition(entityId));
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setRec(null);
        else throw e;
      }
      setBenefits(await api.listBenefits(entityId));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  const recognised = rec?.status === "recognised";

  return (
    <div>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h2>Startup India (DPIIT)</h2>
        {elig && (
          <>
            <p>
              Eligibility:{" "}
              <span className={`badge ${elig.eligible ? "complete" : "active"}`}>
                {elig.eligible ? "eligible" : "not eligible"}
              </span>
            </p>
            <ul className="muted">
              {elig.reasons.map((r, i) => <li key={i}>{r}</li>)}
            </ul>
          </>
        )}
      </div>

      <div className="card">
        <h3>DPIIT recognition</h3>
        {rec && (
          <p className="muted">
            Status: <strong>{rec.status}</strong>
            {rec.dpiit_number ? ` · ${rec.dpiit_number}` : ""}
            {rec.recognised_on ? ` · since ${rec.recognised_on}` : ""}
          </p>
        )}
        <div className="row">
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            {REC_STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, " ")}</option>)}
          </select>
          <input placeholder="DPIIT number" value={dpiit} onChange={(e) => setDpiit(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            onClick={guard(() =>
              api.upsertRecognition(entityId, {
                status,
                dpiit_number: dpiit || null,
                recognised_on: status === "recognised" ? new Date().toISOString().slice(0, 10) : null,
              })
            )}
          >
            Save recognition
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Tax benefits</h3>
        {!recognised ? (
          <p className="muted">DPIIT recognition is required before applying for tax benefits.</p>
        ) : (
          <div className="row">
            <button
              className="secondary"
              style={{ flex: "0 0 auto" }}
              onClick={guard(() => api.applyBenefit(entityId, { type: "section_80iac" }))}
            >
              Apply 80-IAC
            </button>
            <button
              className="secondary"
              style={{ flex: "0 0 auto" }}
              onClick={guard(() => api.applyBenefit(entityId, { type: "angel_tax_56_2_viib" }))}
            >
              Apply angel-tax exemption
            </button>
          </div>
        )}
        {benefits.length > 0 && (
          <table style={{ marginTop: 10 }}>
            <thead><tr><th>Benefit</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {benefits.map((b) => (
                <tr key={b.id}>
                  <td>{BENEFIT_LABELS[b.type] || b.type}</td>
                  <td><span className={`badge ${b.status === "approved" ? "complete" : ""}`}>{b.status}</span></td>
                  <td>
                    {b.status !== "approved" && (
                      <button
                        className="secondary"
                        onClick={guard(() => api.updateBenefitStatus(b.id, { status: "approved" }))}
                      >
                        Mark approved
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

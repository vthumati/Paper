import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api, type PublicKPIRequest } from "../api";

/** Public KPI-submission page for a request's secret link — no login required.
 * The fund shares this link with the company's reporting contact, who submits
 * the period's numbers without needing a Paper account. */
export default function SubmitKpis() {
  const { token = "" } = useParams();
  const [info, setInfo] = useState<PublicKPIRequest | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const [revenue, setRevenue] = useState("");
  const [cash, setCash] = useState("");
  const [burn, setBurn] = useState("");
  const [headcount, setHeadcount] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    api
      .publicKpiRequest(token)
      .then(setInfo)
      .catch((e) => setError((e as Error).message));
  }, [token]);

  if (error && !info) {
    return (
      <div className="container" style={{ maxWidth: 560, margin: "60px auto" }}>
        <div className="card"><p className="error">{error}</p></div>
      </div>
    );
  }
  if (!info) return <div className="container">Loading…</div>;

  const alreadyIn = info.status !== "pending";

  return (
    <div className="container" style={{ maxWidth: 560, margin: "60px auto" }}>
      <div className="card">
        <h1>{info.company_name}</h1>
        <p className="muted">
          KPI report for <strong>{info.period_label}</strong> (as of {info.as_of})
          {info.due_date && <> · due {info.due_date}</>}
        </p>

        {done || alreadyIn ? (
          <>
            <h3>{done ? "Thanks — numbers submitted." : "This period is already submitted."}</h3>
            <p className="muted">
              Your investor will review the figures{done ? " and may reach out with questions." : "."}
            </p>
          </>
        ) : (
          <>
            <h3>Report the period's numbers</h3>
            <label>Revenue for the period (₹)</label>
            <input value={revenue} onChange={(e) => setRevenue(e.target.value)} />
            <label>Cash in bank (₹)</label>
            <input value={cash} onChange={(e) => setCash(e.target.value)} />
            <label>Monthly burn (₹)</label>
            <input value={burn} onChange={(e) => setBurn(e.target.value)} />
            <label>Headcount</label>
            <input value={headcount} onChange={(e) => setHeadcount(e.target.value)} />
            <label>Note (optional)</label>
            <input value={note} onChange={(e) => setNote(e.target.value)} />
            {error && <p className="error">{error}</p>}
            <div style={{ marginTop: 12 }}>
              <button
                disabled={!revenue && !cash && !burn && !headcount}
                onClick={async () => {
                  setError("");
                  try {
                    await api.publicKpiSubmit(token, {
                      revenue: revenue || null,
                      cash: cash || null,
                      monthly_burn: burn || null,
                      headcount: headcount ? Number(headcount) : null,
                      note: note || null,
                    });
                    setDone(true);
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Submit
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

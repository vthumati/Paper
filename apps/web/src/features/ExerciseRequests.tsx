import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import { api, type ExerciseRequestRow, type SecurityClass } from "../api";

/** Employee exercise requests raised in the portal, decided here. */
export default function ExerciseRequests({ entityId }: { entityId: string }) {
  const [reqs, setReqs] = useState<ExerciseRequestRow[]>([]);
  const [classes, setClasses] = useState<SecurityClass[]>([]);
  const [scId, setScId] = useState("");
  const { error, setError, guard } = useGuard(() => load());
  const [note, setNote] = useState("");

  async function load() {
    try {
      const [r, c] = await Promise.all([
        api.listExerciseRequests(entityId),
        api.listSecurityClasses(entityId),
      ]);
      setReqs(r);
      setClasses(c);
      if (!scId && c.length) setScId(c[0].id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  if (reqs.length === 0) return null;

  return (
    <div className="card">
      <h3>Employee exercise requests</h3>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}
      <div className="row">
        <span className="muted" style={{ alignSelf: "center", flex: "0 0 auto" }}>Issue into</span>
        <select value={scId} onChange={(e) => setScId(e.target.value)} style={{ maxWidth: 220 }}>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>
      <table style={{ marginTop: 8 }}>
        <thead>
          <tr><th>Employee</th><th>Options</th><th>Cashless</th><th>Status</th><th></th></tr>
        </thead>
        <tbody>
          {reqs.map((r) => (
            <tr key={r.id}>
              <td>{r.employee}</td>
              <td>{r.quantity.toLocaleString()}</td>
              <td>{r.cashless ? "yes" : "—"}</td>
              <td><span className={`badge ${r.status === "approved" ? "complete" : ""}`}>{r.status}</span></td>
              <td>
                {r.status === "open" && (
                  <>
                    <button
                      disabled={!scId}
                      onClick={guard(async () => {
                        const res = await api.decideExerciseRequest(r.id, {
                          approve: true, security_class_id: scId,
                        });
                        setNote(`Approved — ${res.net_shares?.toLocaleString()} share(s) issued; perquisite ₹${res.perquisite_value} (TDS applies).`);
                      })}
                    >
                      Approve
                    </button>{" "}
                    <button
                      className="secondary"
                      onClick={guard(() => api.decideExerciseRequest(r.id, { approve: false }))}
                    >
                      Reject
                    </button>
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

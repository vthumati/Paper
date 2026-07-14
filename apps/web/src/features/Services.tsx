import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import { api, type Provider, type ServiceEngagement } from "../api";

const CATEGORIES = [
  { v: "cs", label: "Company Secretary" },
  { v: "ca", label: "Chartered Accountant" },
  { v: "lawyer", label: "Lawyer" },
  { v: "valuer", label: "Registered Valuer" },
  { v: "rta", label: "RTA" },
  { v: "fund_admin", label: "Fund Admin" },
];
const STATUSES = ["requested", "accepted", "in_progress", "delivered", "closed"];

export default function Services({ entityId }: { entityId: string }) {
  const [providers, setProviders] = useState<Provider[]>([]);
  const [engagements, setEngagements] = useState<ServiceEngagement[]>([]);
  const { error, setError, guard } = useGuard(() => load());

  // forms
  const [pName, setPName] = useState("");
  const [pCat, setPCat] = useState("cs");
  const [pFirm, setPFirm] = useState("");
  const [provId, setProvId] = useState("");
  const [scope, setScope] = useState("");

  async function load() {
    try {
      const [p, e] = await Promise.all([api.listProviders(), api.listEngagements(entityId)]);
      setProviders(p);
      setEngagements(e);
      if (!provId && p.length) setProvId(p[0].id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  return (
    <div>
      {error && <p className="error">{error}</p>}

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Register provider</h3>
          <p className="muted">Curated partner directory (platform-wide).</p>
          <label>Name</label>
          <input value={pName} onChange={(e) => setPName(e.target.value)} />
          <label>Category</label>
          <select value={pCat} onChange={(e) => setPCat(e.target.value)}>
            {CATEGORIES.map((c) => (
              <option key={c.v} value={c.v}>{c.label}</option>
            ))}
          </select>
          <label>Firm</label>
          <input value={pFirm} onChange={(e) => setPFirm(e.target.value)} />
          <div style={{ marginTop: 10 }}>
            <button
              disabled={!pName}
              onClick={guard(async () => {
                await api.registerProvider({ name: pName, category: pCat, firm: pFirm || null });
                setPName("");
                setPFirm("");
              })}
            >
              Add to directory
            </button>
          </div>
        </div>

        <div className="card" style={{ flex: 2 }}>
          <h3>Engage a provider</h3>
          {providers.length === 0 ? (
            <p className="muted">No providers in the directory yet — add one.</p>
          ) : (
            <>
              <div className="row">
                <div>
                  <label>Provider</label>
                  <select value={provId} onChange={(e) => setProvId(e.target.value)}>
                    {providers.map((p) => (
                      <option key={p.id} value={p.id}>
                        {p.name} ({p.category})
                      </option>
                    ))}
                  </select>
                </div>
              </div>
              <label>Scope of work</label>
              <input
                value={scope}
                onChange={(e) => setScope(e.target.value)}
                placeholder="e.g. FY2026 annual ROC filings"
              />
              <div style={{ marginTop: 10 }}>
                <button
                  disabled={!provId}
                  onClick={guard(async () => {
                    await api.createEngagement(entityId, { provider_id: provId, scope });
                    setScope("");
                  })}
                >
                  Engage
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Engagements</h3>
        {engagements.length === 0 ? (
          <p className="muted">No engagements yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Provider</th>
                <th>Category</th>
                <th>Scope</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {engagements.map((e) => (
                <tr key={e.id}>
                  <td>{e.provider_name}</td>
                  <td>{e.provider_category}</td>
                  <td>{e.scope}</td>
                  <td>
                    <select
                      value={e.status}
                      onChange={(ev) =>
                        guard(() => api.updateEngagement(e.id, { status: ev.target.value }))()
                      }
                    >
                      {STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
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

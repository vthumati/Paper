import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { useNavigate } from "react-router-dom";
import { api, type Alert, type Tenant } from "../api";

export default function Tenants() {
  const nav = useNavigate();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("company");
  const [error, setError] = useState("");

  const load = () => api.listTenants().then(setTenants).catch((e) => setError(e.message));
  useEffect(() => {
    load();
    api.alerts(30).then(setAlerts).catch(() => {});
  }, []);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.createTenant({ name, type });
      setName("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div>
      <h1>Workspaces</h1>

      {alerts.length > 0 && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={{ margin: 0 }}>Alerts ({alerts.length})</h2>
            <button
              className="secondary"
              onClick={async () => {
                await api.sweepAlerts();
                setAlerts(await api.alerts(30));
              }}
            >
              Send reminders
            </button>
          </div>
          {alerts.slice(0, 8).map((a, i) => (
            <div key={i} style={{ borderTop: "1px solid var(--border)", padding: "6px 0" }}>
              {a.overdue ? <span className="badge active">overdue</span> : <span className="badge">due {a.due_date}</span>}{" "}
              {a.title} <span className="muted">· {a.entity_name}</span>
            </div>
          ))}
        </div>
      )}
      <div className="card">
        <h2>Create workspace</h2>
        <form onSubmit={create}>
          <div className="row">
            <div>
              <label>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div style={{ flex: "0 0 160px" }}>
              <label>Type</label>
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="company">Company</option>
                <option value="fund">Fund</option>
                <option value="firm">Firm</option>
              </select>
            </div>
          </div>
          {error && <p className="error">{error}</p>}
          <div style={{ marginTop: 12 }}>
            <button type="submit">Create</button>
          </div>
        </form>
      </div>

      <div className="card">
        <h2>Your workspaces</h2>
        {tenants.length === 0 && (
          <EmptyState icon="🗂️" title="No workspaces yet" hint="Create your first workspace above — a company, fund or firm — to get started." />
        )}
        {tenants.map((t) => (
          <div
            key={t.id}
            className="list-item"
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
            onClick={() => nav(`/tenants/${t.id}/entities`)}
          >
            <span>
              <strong>{t.name}</strong> <span className="badge">{t.type}</span>
            </span>
            <button
              className="secondary"
              style={{ flex: "0 0 auto" }}
              title="Delete this workspace (must be empty)"
              onClick={async (e) => {
                e.stopPropagation();
                if (!window.confirm(`Delete workspace "${t.name}"? This cannot be undone.`)) return;
                setError("");
                try {
                  await api.deleteTenant(t.id);
                  load();
                } catch (err) {
                  setError((err as Error).message);
                }
              }}
            >
              Delete
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

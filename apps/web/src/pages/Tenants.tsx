import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import TeardownDialog from "../components/TeardownDialog";
import { useNavigate } from "react-router-dom";
import { api, type Alert, type Tenant } from "../api";

const TYPE_ICON: Record<string, string> = { company: "🏢", fund: "💰", firm: "⚖️" };

export default function Tenants() {
  const nav = useNavigate();
  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("company");
  const [error, setError] = useState("");
  const [tearing, setTearing] = useState<Tenant | null>(null);
  const [showCreate, setShowCreate] = useState(false);

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
      setShowCreate(false);
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const overdue = alerts.filter((a) => a.overdue).length;

  return (
    <div>
      <div className="hero">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          <div>
            <h1>Your workspaces</h1>
            <p className="hero-sub">
              {tenants.length} workspace{tenants.length === 1 ? "" : "s"}
              {overdue > 0 && ` · ${overdue} compliance item${overdue === 1 ? "" : "s"} overdue`}
            </p>
          </div>
          <button
            onClick={() => setShowCreate((v) => !v)}
            style={{ background: "#fff", color: "var(--accent-strong)" }}
          >
            {showCreate ? "Close" : "＋ New workspace"}
          </button>
        </div>
      </div>

      {showCreate && (
        <div className="card">
          <h2>Create workspace</h2>
          <form onSubmit={create}>
            <div className="row">
              <div>
                <label>Name</label>
                <input value={name} onChange={(e) => setName(e.target.value)} required autoFocus />
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
              <button type="submit">Create workspace</button>
            </div>
          </form>
        </div>
      )}

      {alerts.length > 0 && (
        <div className="card" style={{ borderLeft: "4px solid var(--warn)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
            <h2 style={{ margin: 0 }}>⏰ Compliance alerts ({alerts.length})</h2>
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
            <div key={i} style={{ borderTop: "1px solid var(--border)", padding: "8px 0", display: "flex", alignItems: "center", gap: 8 }}>
              {a.overdue ? <span className="badge danger">overdue</span> : <span className="badge">due {a.due_date}</span>}
              <span>{a.title}</span> <span className="muted">· {a.entity_name}</span>
            </div>
          ))}
        </div>
      )}

      {tenants.length === 0 ? (
        <div className="card">
          <EmptyState
            icon="🗂️"
            title="No workspaces yet"
            hint="Create your first workspace — a company, fund or firm — to get started."
            action={<button onClick={() => setShowCreate(true)}>＋ New workspace</button>}
          />
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 14 }}>
          {tenants.map((t) => (
            <div
              key={t.id}
              className="card"
              style={{ margin: 0, cursor: "pointer", display: "flex", flexDirection: "column", gap: 12 }}
              onClick={() => nav(`/tenants/${t.id}/entities`)}
            >
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <span
                  style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    width: 44, height: 44, borderRadius: 13, background: "var(--light)", fontSize: 22, flex: "0 0 auto",
                  }}
                >
                  {TYPE_ICON[t.type] || "🗂️"}
                </span>
                <div style={{ minWidth: 0 }}>
                  <div style={{ fontWeight: 700, fontSize: 16, color: "var(--heading)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {t.name}
                  </div>
                  <span className="badge" style={{ marginTop: 2 }}>{t.type}</span>
                </div>
              </div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                <span className="muted" style={{ fontWeight: 600, color: "var(--accent-strong)" }}>Open →</span>
                <button
                  className="ghost"
                  style={{ flex: "0 0 auto", fontSize: 13 }}
                  title="Delete this workspace and everything in it"
                  onClick={(e) => {
                    e.stopPropagation();
                    setTearing(t);
                  }}
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tearing && (
        <TeardownDialog
          kind="workspace"
          id={tearing.id}
          name={tearing.name}
          onClose={() => setTearing(null)}
          onDone={() => {
            setTearing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

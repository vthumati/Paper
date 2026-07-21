import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { useNavigate } from "react-router-dom";
import { api, type AdvisorEntity } from "../api";
import Avatar from "../components/Avatar";

/** Advisor console (Mantle-style): a law firm / CA / CS sees every client
 * entity they've been granted access to, across all client organisations,
 * and jumps straight into that company's workspace. */
export default function Advisor() {
  const nav = useNavigate();
  const [entities, setEntities] = useState<AdvisorEntity[]>([]);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    api
      .advisorEntities()
      .then(setEntities)
      .catch((e) => setError(e.message))
      .finally(() => setLoaded(true));
  }, []);

  return (
    <div>
      <p className="muted">
        <a href="#" onClick={(e) => { e.preventDefault(); nav("/"); }}>← Workspaces</a>
      </p>
      <h1>Advisor console</h1>
      {error && <p className="error">{error}</p>}
      {loaded && entities.length === 0 ? (
        <div className="card">
          <EmptyState icon="⚖️" title="No client entities yet" hint="When a company grants your email advisor access, its workspace appears here." />
        </div>
      ) : (
        <div className="card">
          <p className="muted">Client entities you have access to.</p>
          <table>
            <thead>
              <tr><th>Company</th><th>Client org</th><th>As firm</th><th>Access</th><th></th></tr>
            </thead>
            <tbody>
              {entities.map((e) => (
                <tr key={e.entity_id}>
                  <td>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <Avatar name={e.entity_name} /> {e.entity_name}
                    </span>
                  </td>
                  <td className="muted">{e.tenant_name}</td>
                  <td>{e.firm_name}</td>
                  <td><span className={`badge ${e.role === "member" ? "active" : ""}`}>{e.role}</span></td>
                  <td>
                    <button className="secondary" onClick={() => nav(`/entities/${e.entity_id}`)}>
                      Open workspace →
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

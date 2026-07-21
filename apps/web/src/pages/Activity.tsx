import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { useNavigate } from "react-router-dom";
import { api, type AuditEntry } from "../api";

export default function Activity() {
  const nav = useNavigate();
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.auditLog().then(setEntries).catch((e) => setError(e.message));
  }, []);

  return (
    <div>
      <p className="muted">
        <a href="#" onClick={(e) => { e.preventDefault(); nav("/"); }}>
          ← Workspaces
        </a>
      </p>
      <h1>My activity</h1>
      <div className="card">
        <p className="muted">An immutable audit trail of every change you make (NFR-4).</p>
        {error && <p className="error">{error}</p>}
        {entries.length === 0 ? (
          <EmptyState icon="📜" title="No activity yet" hint="Actions across your workspaces — issuances, filings, document generation — are logged here." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>When</th>
                <th>Action</th>
                <th>Path</th>
                <th>Result</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id}>
                  <td className="muted">{new Date(e.created_at).toLocaleString()}</td>
                  <td>{e.method}</td>
                  <td className="muted">{e.path}</td>
                  <td>{e.status_code}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import { api, type AdvisorAccess } from "../api";
import Avatar from "../components/Avatar";

/** Grant external professionals (law firms / CAs / CSs) scoped access to this
 * entity — read-only (viewer) or acting (member) — Mantle-style law-firm
 * collaboration. They reach it from their own cross-tenant advisor console. */
export default function Advisors({ entityId }: { entityId: string }) {
  const [advisors, setAdvisors] = useState<AdvisorAccess[]>([]);
  const [error, setError] = useState("");
  const [email, setEmail] = useState("");
  const [firm, setFirm] = useState("");
  const [role, setRole] = useState<"viewer" | "member">("viewer");

  function load() {
    api.listAdvisorAccess(entityId).then(setAdvisors).catch((e) => setError(e.message));
  }
  useEffect(load, [entityId]);

  const act = (fn: () => Promise<unknown>) => async () => {
    setError("");
    try {
      await fn();
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <PageHeader
        icon="⚖️"
        title="External advisors"
        subtitle="Grant law firms, CAs and CSs scoped access"
      />
      <div className="card">
        <p className="muted">
          Give your law firm, CA or CS scoped access to this company — <strong>viewer</strong> (read-only)
          or <strong>member</strong> (can act, e.g. manage filings). They see it in their own advisor
          console; no membership in your workspace is created.
        </p>
        <div className="row">
          <div>
            <label>Advisor email</label>
            <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="partner@firm.in" />
          </div>
          <div>
            <label>Firm name</label>
            <input value={firm} onChange={(e) => setFirm(e.target.value)} placeholder="Trilegal" />
          </div>
          <div>
            <label>Access</label>
            <select value={role} onChange={(e) => setRole(e.target.value as "viewer" | "member")}>
              <option value="viewer">Viewer (read-only)</option>
              <option value="member">Member (can act)</option>
            </select>
          </div>
        </div>
        <div style={{ marginTop: 10 }}>
          <button
            disabled={!email || !firm}
            onClick={act(async () => {
              await api.grantAdvisorAccess(entityId, { email, firm_name: firm, role });
              setEmail("");
              setFirm("");
            })}
          >
            Grant access
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Advisors with access</h3>
        {advisors.length === 0 ? (
          <EmptyState icon="⚖️" title="No advisors yet" hint="Grant a law firm, CA or CS scoped access by email — they reach this entity from their own advisor console." />
        ) : (
          <table>
            <thead>
              <tr><th>Firm</th><th>Contact</th><th>Access</th><th></th></tr>
            </thead>
            <tbody>
              {advisors.map((a) => (
                <tr key={a.id}>
                  <td>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                      <Avatar name={a.firm_name} /> {a.firm_name}
                    </span>
                  </td>
                  <td className="muted">{a.email}</td>
                  <td><span className={`badge ${a.role === "member" ? "active" : ""}`}>{a.role}</span></td>
                  <td>
                    <button className="secondary" onClick={act(() => api.revokeAdvisorAccess(entityId, a.id))}>
                      Revoke
                    </button>
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

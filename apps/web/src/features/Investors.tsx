import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import {
  api,
  type InvestorAccess,
  type InvestorUpdate,
  type SecondaryRequestRow,
  type Stakeholder,
} from "../api";

export default function Investors({ entityId }: { entityId: string }) {
  const [access, setAccess] = useState<InvestorAccess[]>([]);
  const [updates, setUpdates] = useState<InvestorUpdate[]>([]);
  const [holders, setHolders] = useState<Stakeholder[]>([]);
  const [sales, setSales] = useState<SecondaryRequestRow[]>([]);
  const { error, setError, guard } = useGuard(() => load());

  const [email, setEmail] = useState("");
  const [shId, setShId] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [buyers, setBuyers] = useState<Record<string, string>>({});

  async function load() {
    try {
      const [a, u, sh, sr] = await Promise.all([
        api.listInvestorAccess(entityId),
        api.listInvestorUpdates(entityId),
        api.listStakeholders(entityId),
        api.listSecondaryRequests(entityId),
      ]);
      setAccess(a);
      setUpdates(u);
      setHolders(sh);
      setSales(sr);
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
          <h3>Invite investor</h3>
          <p className="muted">They get a read-only portal showing only their holdings + updates.</p>
          <label>Email</label>
          <input value={email} onChange={(e) => setEmail(e.target.value)} />
          <label>Link to stakeholder (optional)</label>
          <select value={shId} onChange={(e) => setShId(e.target.value)}>
            <option value="">— none —</option>
            {holders.map((h) => (
              <option key={h.id} value={h.id}>{h.name} ({h.type})</option>
            ))}
          </select>
          <div style={{ marginTop: 10 }}>
            <button
              disabled={!email}
              onClick={guard(async () => {
                await api.grantInvestorAccess(entityId, { email, stakeholder_id: shId || null });
                setEmail(""); setShId("");
              })}
            >
              Grant access
            </button>
          </div>
          <ul className="muted">
            {access.map((a) => <li key={a.id}>{a.email} {a.stakeholder_id ? "· linked" : ""}</li>)}
          </ul>
        </div>

        <div className="card" style={{ flex: 1 }}>
          <h3>Publish update</h3>
          <label>Title</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
          <label>Body</label>
          <textarea rows={3} value={body} onChange={(e) => setBody(e.target.value)} />
          <div style={{ marginTop: 10 }}>
            <button
              disabled={!title || !body}
              onClick={guard(async () => {
                await api.publishInvestorUpdate(entityId, { title, body });
                setTitle(""); setBody("");
              })}
            >
              Publish
            </button>
          </div>
        </div>
      </div>

      {sales.length > 0 && (
        <div className="card">
          <h3>Secondary sale requests (ROFR)</h3>
          <p className="muted">
            Investors asked to sell; pick the buyer to exercise the right of first refusal —
            approval executes the transfer (with stamp duty) on the cap table.
          </p>
          <table>
            <thead>
              <tr><th>Seller</th><th>Class</th><th>Qty</th><th>Price</th><th>Status</th><th>Buyer</th><th></th></tr>
            </thead>
            <tbody>
              {sales.map((s) => (
                <tr key={s.id}>
                  <td>{s.seller}</td>
                  <td>{s.security_class}</td>
                  <td>{s.quantity.toLocaleString()}</td>
                  <td>₹{s.price_per_unit}</td>
                  <td><span className={`badge ${s.status === "executed" ? "complete" : ""}`}>{s.status}</span></td>
                  <td>
                    {s.status === "open" ? (
                      <select
                        value={buyers[s.id] ?? ""}
                        onChange={(e) => setBuyers({ ...buyers, [s.id]: e.target.value })}
                      >
                        <option value="">buyer…</option>
                        {holders.filter((h) => h.name !== s.seller).map((h) => (
                          <option key={h.id} value={h.id}>{h.name}</option>
                        ))}
                      </select>
                    ) : (
                      s.buyer ?? "—"
                    )}
                  </td>
                  <td>
                    {s.status === "open" && (
                      <>
                        <button
                          disabled={!buyers[s.id]}
                          onClick={guard(() =>
                            api.decideSecondary(s.id, { approve: true, buyer_stakeholder_id: buyers[s.id] })
                          )}
                        >
                          Approve
                        </button>{" "}
                        <button
                          className="secondary"
                          onClick={guard(() => api.decideSecondary(s.id, { approve: false }))}
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
      )}

      <div className="card">
        <h3>Updates</h3>
        {updates.length === 0 ? (
          <p className="muted">No updates published yet.</p>
        ) : (
          updates.map((u) => (
            <div key={u.id} style={{ borderTop: "1px solid var(--border)", padding: "8px 0" }}>
              <strong>{u.title}</strong> <span className="muted">{new Date(u.created_at).toLocaleDateString()}</span>
              <div className="muted">{u.body}</div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import {
  api,
  type InvestorAccess,
  type InvestorMetrics,
  type InvestorUpdate,
  type SecondaryRequestRow,
  type Stakeholder,
} from "../api";
import EmptyState from "../components/EmptyState";

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
  const [metrics, setMetrics] = useState<InvestorMetrics | null>(null);
  const [period, setPeriod] = useState("");
  const [highlights, setHighlights] = useState("");

  async function load() {
    try {
      const [a, u, sh, sr, m] = await Promise.all([
        api.listInvestorAccess(entityId),
        api.listInvestorUpdates(entityId),
        api.listStakeholders(entityId),
        api.listSecondaryRequests(entityId),
        api.investorReportPreview(entityId).catch(() => null),
      ]);
      setAccess(a);
      setUpdates(u);
      setHolders(sh);
      setSales(sr);
      setMetrics(m);
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
        <h3>Investor report</h3>
        <p className="muted">
          Generate a periodic report combining a live metrics snapshot with your highlights —
          share it via a data room.
        </p>
        {metrics && (
          <div className="row" style={{ gap: 16, flexWrap: "wrap", marginBottom: 8 }}>
            <span className="muted">Shares issued <strong>{metrics.shares_issued.toLocaleString()}</strong></span>
            <span className="muted">FMV <strong>{metrics.fmv_per_share ? `₹${metrics.fmv_per_share}` : "—"}</strong></span>
            <span className="muted">Open rounds <strong>{metrics.open_rounds}</strong></span>
            <span className="muted">Runway <strong>{metrics.runway_months ?? "—"} mo</strong></span>
            <span className="muted">Overdue compliance <strong>{metrics.compliance_overdue}</strong></span>
          </div>
        )}
        <div className="row">
          <div><label>Period</label><input placeholder="Q1 FY26" value={period} onChange={(e) => setPeriod(e.target.value)} /></div>
          <div style={{ flex: 1 }}>
            <label>Highlights</label>
            <textarea rows={2} value={highlights} onChange={(e) => setHighlights(e.target.value)} />
          </div>
          <button
            style={{ flex: "0 0 auto", alignSelf: "flex-end" }}
            disabled={!period}
            onClick={guard(async () => {
              await api.createInvestorReport(entityId, { period_label: period, highlights });
              setPeriod(""); setHighlights("");
              window.alert("Investor report generated — see the Documents tab.");
            })}
          >
            Generate report
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Updates</h3>
        {updates.length === 0 ? (
          <EmptyState icon="📣" title="No updates published yet" hint="Publish an update above — invited investors see it in their portal." />

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

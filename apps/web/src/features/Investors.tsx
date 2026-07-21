import { useEffect, useState } from "react";
import { fmtMoney } from "../lib/format";
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
  const [updPeriod, setUpdPeriod] = useState("");
  const [updHighlights, setUpdHighlights] = useState("");
  const [updLowlights, setUpdLowlights] = useState("");
  const [updAsks, setUpdAsks] = useState("");
  const [updAudience, setUpdAudience] = useState<string[]>([]); // empty = all investors
  const [editingId, setEditingId] = useState<string | null>(null);
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
          <h3>{editingId ? "Edit draft update" : "Compose update"}</h3>
          <p className="muted">
            Structured, data-backed updates — a live metrics snapshot is frozen onto the update
            when you publish.
          </p>
          <div className="row">
            <div style={{ flex: 2 }}>
              <label>Title</label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} />
            </div>
            <div style={{ flex: 1 }}>
              <label>Period</label>
              <input placeholder="Q1 FY27" value={updPeriod} onChange={(e) => setUpdPeriod(e.target.value)} />
            </div>
          </div>
          <label>Body</label>
          <textarea rows={2} value={body} onChange={(e) => setBody(e.target.value)} />
          <div className="row">
            <div style={{ flex: 1 }}>
              <label>Highlights</label>
              <textarea rows={2} value={updHighlights} onChange={(e) => setUpdHighlights(e.target.value)} />
            </div>
            <div style={{ flex: 1 }}>
              <label>Lowlights</label>
              <textarea rows={2} value={updLowlights} onChange={(e) => setUpdLowlights(e.target.value)} />
            </div>
          </div>
          <label>Asks</label>
          <input placeholder="Intros, hiring, help…" value={updAsks} onChange={(e) => setUpdAsks(e.target.value)} />
          {access.length > 0 && (
            <>
              <label>
                Audience{" "}
                <span className="muted" style={{ fontWeight: 400 }}>
                  — leave empty for all invited investors; pick emails to restrict (Ctrl-click for several)
                </span>
              </label>
              <select
                multiple
                size={Math.min(4, access.length)}
                value={updAudience}
                onChange={(e) =>
                  setUpdAudience(Array.from(e.target.selectedOptions).map((o) => o.value))
                }
              >
                {access.map((a) => (
                  <option key={a.id} value={a.email}>{a.email}</option>
                ))}
              </select>
              {updAudience.length > 0 && (
                <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>
                  Restricted to {updAudience.length} investor{updAudience.length === 1 ? "" : "s"} ·{" "}
                  <a href="#" onClick={(e) => { e.preventDefault(); setUpdAudience([]); }}>send to everyone</a>
                </p>
              )}
            </>
          )}
          <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
            {(() => {
              const payload = {
                title,
                body,
                period_label: updPeriod || null,
                highlights: updHighlights || null,
                lowlights: updLowlights || null,
                asks: updAsks || null,
                audience: updAudience.length ? updAudience : null,
              };
              const clear = () => {
                setTitle(""); setBody(""); setUpdPeriod("");
                setUpdHighlights(""); setUpdLowlights(""); setUpdAsks("");
                setUpdAudience([]);
                setEditingId(null);
              };
              return (
                <>
                  <button
                    disabled={!title || !body}
                    onClick={guard(async () => {
                      if (editingId) {
                        await api.editInvestorUpdate(editingId, payload);
                        await api.publishInvestorUpdateDraft(editingId);
                      } else {
                        await api.publishInvestorUpdate(entityId, { ...payload, publish: true });
                      }
                      clear();
                    })}
                  >
                    Publish
                  </button>
                  <button
                    className="secondary"
                    disabled={!title || !body}
                    onClick={guard(async () => {
                      if (editingId) await api.editInvestorUpdate(editingId, payload);
                      else await api.publishInvestorUpdate(entityId, { ...payload, publish: false });
                      clear();
                    })}
                  >
                    Save draft
                  </button>
                  {editingId && (
                    <button className="secondary" onClick={clear}>Cancel</button>
                  )}
                </>
              );
            })()}
          </div>

          {(title || body) && (
            <div style={{ marginTop: 12 }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
                Preview — how investors will see it in their portal
              </div>
              <div style={{ border: "1px solid var(--border)", borderRadius: "var(--radius-sm)", background: "var(--light)", padding: 12 }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <strong>{title || "Untitled update"}</strong>
                  {updPeriod && <span className="badge">{updPeriod}</span>}
                  <span className="muted" style={{ fontSize: 12 }}>{new Date().toLocaleDateString()}</span>
                </div>
                {body && <div className="muted" style={{ marginTop: 4 }}>{body}</div>}
                {updHighlights && <div className="muted">🌟 {updHighlights}</div>}
                {updLowlights && <div className="muted">⚠️ {updLowlights}</div>}
                {updAsks && <div className="muted">🙏 {updAsks}</div>}
                {metrics && (
                  <div className="row" style={{ gap: 12, flexWrap: "wrap", marginTop: 6 }}>
                    <span className="muted">Shares <strong>{metrics.shares_issued.toLocaleString()}</strong></span>
                    <span className="muted">FMV <strong>{metrics.fmv_per_share ? `₹${metrics.fmv_per_share}` : "—"}</strong></span>
                    <span className="muted">Runway <strong>{metrics.runway_months ?? "—"} mo</strong></span>
                    <span className="muted" style={{ fontSize: 11 }}>(metrics frozen at publish)</span>
                  </div>
                )}
              </div>
            </div>
          )}
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
                  <td>{fmtMoney(s.price_per_unit)}</td>
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

      {(() => {
        const published = updates.filter((u) => u.status !== "draft");
        if (published.length === 0 || access.length === 0) return null;
        const rows = published.map((u) => {
          const opened = (u.viewers ?? []).length;
          return { title: u.title, recipients: u.audience?.length ?? access.length, opened };
        });
        const totals = rows.reduce(
          (s, r) => ({ recipients: s.recipients + r.recipients, opened: s.opened + r.opened }),
          { recipients: 0, opened: 0 }
        );
        const rate = (o: number, r: number) => (r ? `${Math.round((o / r) * 1000) / 10}%` : "—");
        return (
          <div className="card">
            <h3>Update engagement</h3>
            <p className="muted" style={{ marginTop: 0 }}>
              Who's actually reading — recipients are your invited investors; opens are recorded
              when they read an update in the portal.
            </p>
            <table>
              <thead>
                <tr><th>Update</th><th>Recipients</th><th>Opened</th><th>Opening rate</th></tr>
              </thead>
              <tbody>
                <tr style={{ background: "var(--light)" }}>
                  <td style={{ fontWeight: 700, color: "var(--heading)" }}>ALL UPDATES</td>
                  <td style={{ fontWeight: 600 }}>{totals.recipients}</td>
                  <td style={{ fontWeight: 600 }}>{totals.opened}</td>
                  <td style={{ fontWeight: 600 }}>{rate(totals.opened, totals.recipients)}</td>
                </tr>
                {rows.map((r) => (
                  <tr key={r.title + r.recipients}>
                    <td>{r.title}</td>
                    <td>{r.recipients}</td>
                    <td>{r.opened}</td>
                    <td>{rate(r.opened, r.recipients)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}

      <div className="card">
        <h3>Updates</h3>
        {updates.length === 0 ? (
          <EmptyState icon="📣" title="No updates published yet" hint="Publish an update above — invited investors see it in their portal." />

        ) : (
          updates.map((u) => {
            const viewers = u.viewers ?? [];
            const opens = viewers.reduce((n, v) => n + v.view_count, 0);
            return (
              <div key={u.id} style={{ borderTop: "1px solid var(--border)", padding: "8px 0" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
                  <strong>{u.title}</strong>
                  {u.period_label && <span className="badge">{u.period_label}</span>}
                  <span className={`badge ${u.status === "published" ? "complete" : ""}`}>{u.status}</span>
                  {u.audience && (
                    <span className="badge" title={u.audience.join("\n")}>
                      → {u.audience.length} investor{u.audience.length === 1 ? "" : "s"}
                    </span>
                  )}
                  <span className="muted">{new Date(u.created_at).toLocaleDateString()}</span>
                  {u.status === "published" && (
                    <span
                      className="muted"
                      title={viewers.map((v) => `${v.email} · ${v.view_count}×`).join("\n") || "No opens yet"}
                    >
                      👁 {viewers.length} viewer{viewers.length === 1 ? "" : "s"} · {opens} open{opens === 1 ? "" : "s"}
                    </span>
                  )}
                  {u.status === "draft" && (
                    <span style={{ display: "flex", gap: 6 }}>
                      <button
                        className="secondary"
                        onClick={() => {
                          setEditingId(u.id);
                          setTitle(u.title); setBody(u.body);
                          setUpdPeriod(u.period_label ?? "");
                          setUpdHighlights(u.highlights ?? "");
                          setUpdLowlights(u.lowlights ?? "");
                          setUpdAsks(u.asks ?? "");
                          setUpdAudience(u.audience ?? []);
                        }}
                      >
                        Edit
                      </button>
                      <button onClick={guard(() => api.publishInvestorUpdateDraft(u.id))}>Publish</button>
                    </span>
                  )}
                </div>
                <div className="muted">{u.body}</div>
                {u.highlights && <div className="muted">🌟 {u.highlights}</div>}
                {u.lowlights && <div className="muted">⚠️ {u.lowlights}</div>}
                {u.asks && <div className="muted">🙏 {u.asks}</div>}
                {u.metrics && (
                  <div className="row" style={{ gap: 12, flexWrap: "wrap", marginTop: 4 }}>
                    <span className="muted">Shares <strong>{Number(u.metrics.shares_issued ?? 0).toLocaleString()}</strong></span>
                    <span className="muted">FMV <strong>{u.metrics.fmv_per_share ? `₹${u.metrics.fmv_per_share}` : "—"}</strong></span>
                    <span className="muted">Runway <strong>{u.metrics.runway_months ?? "—"} mo</strong></span>
                    <span className="muted">Burn <strong>{u.metrics.monthly_burn ? fmtMoney(String(u.metrics.monthly_burn)) : "—"}</strong></span>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}

import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import { useGuard } from "../hooks";
import { api, ApiError, type AdminSubscription } from "../api";

const TIERS = ["basic", "growth", "scale"];
const AUDIT_TYPES = [
  { v: "corporate_audit", label: "Corporate audit" },
  { v: "pre_diligence", label: "Pre-diligence audit" },
  { v: "cleanup", label: "Clean-up" },
];
const AUDIT_STATUSES = ["scheduled", "in_progress", "completed"];

export default function Admin({ entityId }: { entityId: string }) {
  const [sub, setSub] = useState<AdminSubscription | null>(null);
  const { error, setError, guard } = useGuard(() => load());

  const [tier, setTier] = useState("growth");
  const [tpDate, setTpDate] = useState("2026-06-30");
  const [tpSummary, setTpSummary] = useState("");
  const [auditType, setAuditType] = useState("corporate_audit");
  const [auditPeriod, setAuditPeriod] = useState("FY2026");

  async function load() {
    try {
      setSub(await api.getSubscription(entityId));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) setSub(null);
      else setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  if (!sub) {
    return (
      <div>
        {error && <p className="error">{error}</p>}
        <PageHeader
          icon="🏢"
          title="Managed Corporate Administration"
          subtitle="Managed cap-table upkeep, touchpoints and annual audits"
        />
        <div className="card">
          <p className="muted">
            Subscribe for managed cap-table/record upkeep, quarterly touchpoints, and annual audits.
          </p>
          <label>Tier</label>
          <select value={tier} onChange={(e) => setTier(e.target.value)} style={{ maxWidth: 200 }}>
            {TIERS.map((t) => (
              <option key={t} value={t}>{t}</option>
            ))}
          </select>
          <div style={{ marginTop: 10 }}>
            <button onClick={guard(() => api.subscribe(entityId, { tier }))}>Subscribe</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <PageHeader
        icon="🏢"
        title="Managed Administration"
        subtitle="Cap-table upkeep, touchpoints and annual audits"
        right={
          <>
            <span className="badge">{sub.tier}</span>
            <span className="badge complete">{sub.status}</span>
          </>
        }
      />

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Log touchpoint</h3>
          <label>Date</label>
          <input type="date" value={tpDate} onChange={(e) => setTpDate(e.target.value)} />
          <label>Summary</label>
          <input value={tpSummary} onChange={(e) => setTpSummary(e.target.value)} />
          <div style={{ marginTop: 10 }}>
            <button
              onClick={guard(async () => {
                await api.addTouchpoint(sub.id, {
                  date: tpDate,
                  attendee: "Paralegal",
                  summary: tpSummary,
                });
                setTpSummary("");
              })}
            >
              Log
            </button>
          </div>
        </div>

        <div className="card" style={{ flex: 1 }}>
          <h3>Schedule audit</h3>
          <label>Type</label>
          <select value={auditType} onChange={(e) => setAuditType(e.target.value)}>
            {AUDIT_TYPES.map((a) => (
              <option key={a.v} value={a.v}>{a.label}</option>
            ))}
          </select>
          <label>Period</label>
          <input value={auditPeriod} onChange={(e) => setAuditPeriod(e.target.value)} />
          <div style={{ marginTop: 10 }}>
            <button
              onClick={guard(() =>
                api.scheduleAudit(sub.id, { type: auditType, period_label: auditPeriod })
              )}
            >
              Schedule
            </button>
          </div>
        </div>
      </div>

      <div className="card">
        <h3>Touchpoints</h3>
        {sub.touchpoints.length === 0 ? (
          <EmptyState icon="📇" title="No touchpoints yet" hint="Log client meetings and calls here as they happen." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Date</th>
                <th>Attendee</th>
                <th>Summary</th>
              </tr>
            </thead>
            <tbody>
              {sub.touchpoints.map((t) => (
                <tr key={t.id}>
                  <td>{t.date}</td>
                  <td>{t.attendee}</td>
                  <td>{t.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Audit engagements</h3>
        {sub.audits.length === 0 ? (
          <EmptyState icon="🧾" title="No audit engagements yet" hint="Audit engagements you record for this subscription appear here." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Type</th>
                <th>Period</th>
                <th>Status</th>
                <th>Findings</th>
              </tr>
            </thead>
            <tbody>
              {sub.audits.map((a) => (
                <tr key={a.id}>
                  <td>{a.type}</td>
                  <td>{a.period_label}</td>
                  <td>
                    <select
                      value={a.status}
                      onChange={(ev) =>
                        guard(() => api.updateAudit(sub.id, a.id, { status: ev.target.value }))()
                      }
                    >
                      {AUDIT_STATUSES.map((s) => (
                        <option key={s} value={s}>{s}</option>
                      ))}
                    </select>
                  </td>
                  <td>{a.findings || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

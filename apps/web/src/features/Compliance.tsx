import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import { api, type Obligation, type TaxRecord } from "../api";
import ProgressRing from "../components/ProgressRing";

const STATUSES = ["due", "in_prep", "filed", "acknowledged"];
const TAX_TYPES = [
  { v: "gst", label: "GST" },
  { v: "tds", label: "TDS" },
  { v: "form16", label: "Form 16/16A" },
  { v: "itr", label: "ITR" },
  { v: "other", label: "Other" },
];

export default function Compliance({
  entityId,
  entityType,
}: {
  entityId: string;
  entityType?: string;
}) {
  const [obs, setObs] = useState<Obligation[]>([]);
  const [health, setHealth] = useState<{ total: number; filed: number; overdue: number; score: number } | null>(null);
  const [fyEnd, setFyEnd] = useState("2026-03-31");
  const [error, setError] = useState("");

  // tax-filing archive
  const [taxRecords, setTaxRecords] = useState<TaxRecord[]>([]);
  const [tType, setTType] = useState("gst");
  const [tPeriod, setTPeriod] = useState("Q1 FY2026");
  const [tRef, setTRef] = useState("");
  const [tAmt, setTAmt] = useState("");

  const load = async () => {
    try {
      setObs(await api.listCompliance(entityId));
      setHealth(await api.complianceHealth(entityId));
      setTaxRecords(await api.listTaxRecords(entityId));
    } catch (e) {
      setError((e as Error).message);
    }
  };
  useEffect(() => {
    load();
  }, [entityId]);

  async function generate() {
    setError("");
    try {
      await api.generateCompliance(entityId, { financial_year_end: fyEnd });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function generatePeriodic() {
    setError("");
    try {
      await api.generatePeriodicCompliance(entityId, { financial_year_end: fyEnd });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function generateAif() {
    setError("");
    try {
      await api.generateAifCompliance(entityId, { financial_year_end: fyEnd });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function setStatus(id: string, status: string) {
    setError("");
    try {
      await api.updateObligation(id, { status });
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <PageHeader
        icon="🗂️"
        title="Compliance calendar"
        subtitle="Statutory ROC, GST and TDS obligations and filings"
      />
      <div className="card">
        <p className="muted">
          Generate statutory ROC obligations from the financial-year end (assumes a 31-March FY).
        </p>
        <div className="row">
          <div style={{ flex: "0 0 200px" }}>
            <label>Financial year end</label>
            <input type="date" value={fyEnd} onChange={(e) => setFyEnd(e.target.value)} />
          </div>
          <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
            <button onClick={generate}>Generate annual ROC</button>
          </div>
          <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
            <button className="secondary" onClick={generatePeriodic}>Generate GST/TDS schedule</button>
          </div>
          {(entityType === "fund" || entityType === "spv") && (
            <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
              <button className="secondary" onClick={generateAif}>Generate SEBI AIF calendar</button>
            </div>
          )}
          <div style={{ flex: "0 0 auto", alignSelf: "flex-end" }}>
            <button className="secondary" onClick={() => api.downloadComplianceCsv(entityId)}>Export CSV</button>
          </div>
        </div>
        {health && health.total > 0 && (
          <div className="row" style={{ alignItems: "center", gap: 20, marginTop: 10 }}>
            <ProgressRing value={health.score} label="compliance health" size={110} />
            <p className="muted">
              {health.filed}/{health.total} filed ·{" "}
              {health.overdue > 0 ? (
                <span className="badge active">{health.overdue} overdue</span>
              ) : (
                <span className="badge complete">none overdue</span>
              )}
            </p>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Obligations</h3>
        {obs.length === 0 ? (
          <EmptyState icon="🗂️" title="No obligations yet" hint="Generate the ROC and GST/TDS calendar above to populate statutory due dates and track filing status." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Form</th>
                <th>Title</th>
                <th>Category</th>
                <th>Period</th>
                <th>Due</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {obs.map((o) => (
                <tr key={o.id}>
                  <td>{o.form_code}</td>
                  <td>{o.title}</td>
                  <td>{o.category}</td>
                  <td>{o.period_label}</td>
                  <td>
                    {o.due_date}{" "}
                    {o.overdue && <span className="badge active">overdue</span>}
                  </td>
                  <td>
                    <select value={o.status} onChange={(e) => setStatus(o.id, e.target.value)}>
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

      <div className="card">
        <h3>Tax filings</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Keep a reference archive of filed GST / TDS / income-tax returns.
        </p>
        <div className="row">
          <select value={tType} onChange={(e) => setTType(e.target.value)}>
            {TAX_TYPES.map((t) => <option key={t.v} value={t.v}>{t.label}</option>)}
          </select>
          <input placeholder="Period" value={tPeriod} onChange={(e) => setTPeriod(e.target.value)} />
          <input placeholder="Reference" value={tRef} onChange={(e) => setTRef(e.target.value)} />
          <input placeholder="Amount ₹" value={tAmt} onChange={(e) => setTAmt(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!tPeriod}
            onClick={async () => {
              setError("");
              try {
                await api.addTaxRecord(entityId, {
                  type: tType,
                  period_label: tPeriod,
                  reference: tRef || null,
                  amount: tAmt || null,
                });
                setTRef(""); setTAmt("");
                await load();
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Add
          </button>
        </div>
        {taxRecords.length > 0 && (
          <table style={{ marginTop: 10 }}>
            <thead>
              <tr><th>Type</th><th>Period</th><th>Reference</th><th>Amount</th></tr>
            </thead>
            <tbody>
              {taxRecords.map((r) => (
                <tr key={r.id}>
                  <td>{r.type}</td>
                  <td>{r.period_label}</td>
                  <td>{r.reference || "—"}</td>
                  <td>{r.amount ? `₹${r.amount}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

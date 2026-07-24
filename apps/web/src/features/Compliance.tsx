import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import { api, type FemaTracker, type Obligation, type TaxRecord } from "../api";
import ProgressRing from "../components/ProgressRing";

const STATUSES = ["due", "in_prep", "filed", "acknowledged"];
// obligations whose statutory form we can pre-fill from the ledger/governance
const PREFILLABLE = new Set(["PAS-3", "MGT-14", "FC-GPR"]);
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
  // FEMA tracker + SH-7
  const [fema, setFema] = useState<FemaTracker | null>(null);
  const [shCap, setShCap] = useState("");

  const load = async () => {
    try {
      setObs(await api.listCompliance(entityId));
      setHealth(await api.complianceHealth(entityId));
      setTaxRecords(await api.listTaxRecords(entityId));
      setFema(await api.femaTracker(entityId));
    } catch (e) {
      setError((e as Error).message);
    }
  };

  async function prefill(o: Obligation) {
    setError("");
    try {
      const doc = await api.prefillObligation(o.id);
      api.downloadDocumentPdf(doc.id, doc.title);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }
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
                <th>Form</th>
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
                  <td style={{ whiteSpace: "nowrap" }}>
                    {o.document_id ? (
                      <button className="secondary" onClick={() => api.downloadDocumentPdf(o.document_id!, o.form_code)}>
                        ⬇ Form
                      </button>
                    ) : PREFILLABLE.has(o.form_code) ? (
                      <button className="secondary" onClick={() => prefill(o)}>Pre-fill</button>
                    ) : (
                      "—"
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>MCA form pre-fillers</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Draft statutory forms straight from the equity ledger. Increase authorised capital to
          generate SH-7 (and record the filing); PAS-3 / MGT-14 / FC-GPR pre-fill from the
          "Pre-fill" action on each obligation above.
        </p>
        <div className="row" style={{ alignItems: "flex-end" }}>
          <div>
            <label>New authorised capital (₹) — SH-7</label>
            <input value={shCap} onChange={(e) => setShCap(e.target.value)} placeholder="e.g. 5000000" />
          </div>
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!shCap}
            onClick={async () => {
              setError("");
              try {
                const doc = await api.generateSH7(entityId, { new_authorised_capital: shCap });
                api.downloadDocumentPdf(doc.id, "SH-7");
                setShCap("");
                await load();
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Generate SH-7
          </button>
          <button className="secondary" style={{ flex: "0 0 auto" }}
            onClick={async () => { try { const d = await api.generatePas3(entityId); api.downloadDocumentPdf(d.id, "PAS-3"); } catch (e) { setError((e as Error).message); } }}>
            Generate PAS-3
          </button>
        </div>
      </div>

      {fema && (
        <div className="card">
          <h3>FEMA / RBI tracker</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            Cross-border funding: FC-GPR reporting for foreign investment, and the Single Master
            Form (SMF) checklist.
          </p>
          <div className="row" style={{ gap: 24, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 260px" }}>
              <label>Non-resident holders ({fema.non_resident_holders.length})</label>
              {fema.non_resident_holders.length === 0 ? (
                <p className="muted" style={{ fontSize: 13 }}>None on the register.</p>
              ) : (
                fema.non_resident_holders.map((n) => (
                  <div key={n.id} style={{ fontSize: 13 }}>
                    {n.name} <span className="muted">· {n.country ?? n.nationality ?? "non-resident"}</span>
                  </div>
                ))
              )}
              <button className="secondary" style={{ marginTop: 8 }}
                onClick={async () => { try { const d = await api.generateFcGpr(entityId); api.downloadDocumentPdf(d.id, "FC-GPR"); } catch (e) { setError((e as Error).message); } }}>
                Generate FC-GPR
              </button>
            </div>
            <div style={{ flex: "1 1 300px" }}>
              <label>Single Master Form (SMF) checklist</label>
              <ol style={{ margin: "4px 0 0", paddingLeft: 18, fontSize: 13 }}>
                {fema.smf_checklist.map((s, i) => <li key={i} style={{ marginBottom: 3 }}>{s}</li>)}
              </ol>
            </div>
          </div>
        </div>
      )}

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

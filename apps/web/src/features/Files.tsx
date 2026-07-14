import { useEffect, useState } from "react";
import { api, type FileItem, type TaxRecord } from "../api";

const TAX_TYPES = [
  { v: "gst", label: "GST" },
  { v: "tds", label: "TDS" },
  { v: "form16", label: "Form 16/16A" },
  { v: "itr", label: "ITR" },
  { v: "other", label: "Other" },
];

export default function Files({ entityId }: { entityId: string }) {
  const [files, setFiles] = useState<FileItem[]>([]);
  const [q, setQ] = useState("");
  const [taxRecords, setTaxRecords] = useState<TaxRecord[]>([]);
  const [error, setError] = useState("");

  // tax form
  const [tType, setTType] = useState("gst");
  const [tPeriod, setTPeriod] = useState("Q1 FY2026");
  const [tRef, setTRef] = useState("");
  const [tAmt, setTAmt] = useState("");

  async function loadFiles(query = "") {
    try {
      setFiles(await api.files(entityId, query || undefined));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function loadTax() {
    try {
      setTaxRecords(await api.listTaxRecords(entityId));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    loadFiles();
    loadTax();
  }, [entityId]);

  return (
    <div>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h2>File cabinet</h2>
        <p className="muted">Every generated document across the workspace, in one place.</p>
        <div className="row">
          <input
            placeholder="Search documents…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && loadFiles(q)}
          />
          <button style={{ flex: "0 0 auto" }} onClick={() => loadFiles(q)}>Search</button>
          {q && (
            <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => { setQ(""); loadFiles(); }}>
              Clear
            </button>
          )}
        </div>
        {files.length === 0 ? (
          <p className="muted">No documents.</p>
        ) : (
          <table style={{ marginTop: 10 }}>
            <thead>
              <tr><th>Title</th><th>Type</th><th>Source</th><th>Status</th><th>v</th></tr>
            </thead>
            <tbody>
              {files.map((f) => (
                <tr key={f.id}>
                  <td>{f.title}</td>
                  <td className="muted">{f.type}</td>
                  <td className="muted">{f.subject_type || "—"}</td>
                  <td><span className={`badge ${f.status === "signed" ? "signed" : ""}`}>{f.status}</span></td>
                  <td>{f.current_version}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Tax records</h3>
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
                await loadTax();
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

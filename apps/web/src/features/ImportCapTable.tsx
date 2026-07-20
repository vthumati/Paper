import { useState } from "react";
import { fmtMoney } from "../lib/format";
import { api, type CapTableImportReport } from "../api";

/** CSV onboarding: pick a file, validate (dry run), then apply atomically. */
export default function ImportCapTable({
  entityId,
  onApplied,
}: {
  entityId: string;
  onApplied?: () => void;
}) {
  const [csv, setCsv] = useState("");
  const [fileName, setFileName] = useState("");
  const [report, setReport] = useState<CapTableImportReport | null>(null);
  const [error, setError] = useState("");

  const readFile = (f: File) => {
    const reader = new FileReader();
    reader.onload = () => {
      setCsv(String(reader.result ?? ""));
      setFileName(f.name);
      setReport(null);
    };
    reader.readAsText(f);
  };

  const run = (apply: boolean) => async () => {
    setError("");
    try {
      const r = await api.importCapTable(entityId, csv, apply);
      setReport(r);
      if (r.applied) onApplied?.();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="card">
      <h3>Import cap table (CSV)</h3>
      <p className="muted">
        Onboard an existing cap table: stakeholders and share classes are created as
        needed, issuances land on the ledger.{" "}
        <a href="#" onClick={(e) => { e.preventDefault(); api.downloadImportTemplate(entityId); }}>
          Download the template
        </a>{" "}
        to see the expected columns.
      </p>
      {error && <p className="error">{error}</p>}
      <div className="row" style={{ alignItems: "center" }}>
        <input
          type="file"
          accept=".csv,text/csv"
          onChange={(e) => e.target.files?.[0] && readFile(e.target.files[0])}
        />
        <button style={{ flex: "0 0 auto" }} disabled={!csv} onClick={run(false)}>
          Validate
        </button>
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!csv || !report?.valid || report?.applied}
          onClick={run(true)}
        >
          Apply import
        </button>
      </div>
      {fileName && <p className="muted">{fileName}</p>}

      {report && !report.valid && (
        <>
          <p className="error">CSV has errors — fix them and validate again. Nothing was imported.</p>
          <ul className="muted">
            {report.errors.map((e, i) => (
              <li key={i}>Row {e.row}: {e.error}</li>
            ))}
          </ul>
        </>
      )}
      {report && report.valid && report.summary && (
        <p className={report.applied ? "" : "muted"}>
          {report.applied ? "Imported: " : "Ready to import: "}
          <strong>{report.summary.issuances}</strong> issuance(s) ·{" "}
          {report.summary.total_shares.toLocaleString()} shares · {fmtMoney(report.summary.total_invested)} invested
          {report.summary.classes_to_create.length > 0 && (
            <> · new classes: {report.summary.classes_to_create.join(", ")}</>
          )}
          {report.summary.stakeholders_to_create.length > 0 && (
            <> · new stakeholders: {report.summary.stakeholders_to_create.length}</>
          )}
          {report.summary.warning && <span className="error"> — {report.summary.warning}</span>}
          {report.applied && " ✓"}
        </p>
      )}
    </div>
  );
}

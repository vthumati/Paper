import { useState } from "react";
import { api, type TermSheetScan } from "../api";

const SEV_LABEL: Record<string, string> = { red: "Off-market", amber: "Push back", ok: "Standard" };

/** Highlight each finding's matched clause inside the (whitespace-normalised)
 * pasted text — Pulley-style document-plus-summary view. */
function highlightSegments(
  text: string,
  findings: TermSheetScan["findings"]
): { text: string; severity?: string }[] {
  const norm = text.replace(/\s+/g, " ");
  const marks: { start: number; end: number; severity: string }[] = [];
  for (const f of findings) {
    if (!f.snippet) continue;
    const core = f.snippet.replace(/^…/, "").replace(/…$/, "").trim();
    if (core.length < 8) continue;
    const at = norm.toLowerCase().indexOf(core.toLowerCase());
    if (at >= 0) marks.push({ start: at, end: at + core.length, severity: f.severity });
  }
  marks.sort((a, b) => a.start - b.start);
  // snippets carry surrounding context, so neighbouring findings overlap —
  // merge overlaps into one region, keeping the strongest severity
  const rank = { red: 0, amber: 1, ok: 2 } as Record<string, number>;
  const merged: typeof marks = [];
  for (const m of marks) {
    const last = merged[merged.length - 1];
    if (last && m.start <= last.end) {
      last.end = Math.max(last.end, m.end);
      if (rank[m.severity] < rank[last.severity]) last.severity = m.severity;
    } else {
      merged.push({ ...m });
    }
  }
  const out: { text: string; severity?: string }[] = [];
  let pos = 0;
  for (const m of merged) {
    if (m.start > pos) out.push({ text: norm.slice(pos, m.start) });
    out.push({ text: norm.slice(m.start, m.end), severity: m.severity });
    pos = m.end;
  }
  if (pos < norm.length) out.push({ text: norm.slice(pos) });
  return out;
}

export default function TermSheetScanner({ entityId }: { entityId: string }) {
  const [text, setText] = useState("");
  const [scan, setScan] = useState<TermSheetScan | null>(null);
  const [error, setError] = useState("");

  return (
    <div className="card">
      <h3>Term sheet scanner</h3>
      <p className="muted">
        Paste a term sheet to flag off-market terms against the India-market standard —
        rules-based and explainable, not legal advice.
      </p>
      <textarea
        rows={6}
        style={{ width: "100%", fontFamily: "inherit" }}
        placeholder="Paste the term sheet text here…"
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <div style={{ marginTop: 8 }}>
        <button
          disabled={text.trim().length < 20}
          onClick={async () => {
            setError("");
            try {
              setScan(await api.scanTermSheet(entityId, text));
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Scan
        </button>
      </div>
      {error && <p className="error">{error}</p>}

      {scan && (
        <div style={{ marginTop: 12 }}>
          <p>
            <strong>{scan.verdict}</strong>{" "}
            <span className="muted">
              ({scan.counts.red} off-market · {scan.counts.amber} push-back ·{" "}
              {scan.counts.ok} standard, {scan.rules_run} rules run)
            </span>
          </p>
          <div className="row">
            <div style={{ flex: 1.2, minWidth: 300 }}>
              <label>Your term sheet — flagged clauses highlighted</label>
              <div className="paper-sheet" style={{ fontSize: 13, padding: "20px 24px" }}>
                {highlightSegments(text, scan.findings).map((seg, i) =>
                  seg.severity ? (
                    <mark key={i} className={seg.severity}>{seg.text}</mark>
                  ) : (
                    <span key={i}>{seg.text}</span>
                  )
                )}
              </div>
            </div>
            <div style={{ flex: 1, minWidth: 280 }}>
              <label>Findings</label>
              {scan.findings.map((f) => (
            <div key={f.code} style={{ borderTop: "1px solid var(--border)", padding: "8px 0" }}>
              <span
                className={`badge ${
                  f.severity === "ok" ? "complete" : f.severity === "red" ? "danger" : "active"
                }`}
              >
                {SEV_LABEL[f.severity]}
              </span>{" "}
              <strong>{f.title}</strong>
              <div className="muted" style={{ marginTop: 4 }}>{f.detail}</div>
            </div>
          ))}
            </div>
          </div>
          <p className="muted" style={{ marginTop: 8 }}>{scan.disclaimer}</p>
        </div>
      )}
    </div>
  );
}

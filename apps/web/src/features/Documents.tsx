import { useEffect, useState } from "react";
import { api, type Document, type DocTemplate } from "../api";
import { placeholders, renderPreview } from "../lib/templates";

export default function Documents({ entityId }: { entityId: string }) {
  const [templates, setTemplates] = useState<DocTemplate[]>([]);
  const [docs, setDocs] = useState<Document[]>([]);
  const [selected, setSelected] = useState<Document | null>(null);
  const [tplKey, setTplKey] = useState("");
  const [values, setValues] = useState<Record<string, string>>({});
  const [error, setError] = useState("");

  async function load() {
    try {
      const [t, d] = await Promise.all([api.listTemplates(), api.listDocuments(entityId)]);
      setTemplates(t);
      setDocs(d);
      if (!tplKey && t.length) setTplKey(t[0].key);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  async function create() {
    setError("");
    try {
      const doc = await api.createDocument(entityId, { template_key: tplKey, data: values });
      setSelected(doc);
      setValues({});
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const tpl = templates.find((t) => t.key === tplKey);
  const fields = tpl ? placeholders(tpl.body) : [];
  const missing = fields.filter((f) => !values[f]?.trim());

  async function requestSignature() {
    if (!selected) return;
    setError("");
    try {
      const sig = await api.requestSignature(selected.id, {
        signatories: [{ name: "Authorised signatory", email: "signer@example.in" }],
      });
      // simulate the verified e-sign provider callback (HLD §9.4)
      await api.completeSignature(sig.id);
      setSelected(await api.getDocument(selected.id));
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>Generate document</h2>
        <div className="row">
          <div style={{ flex: 1, minWidth: 260 }}>
            <label>Template</label>
            <select
              value={tplKey}
              onChange={(e) => { setTplKey(e.target.value); setValues({}); }}
            >
              {templates.map((t) => (
                <option key={t.key} value={t.key}>{t.name}</option>
              ))}
            </select>
            {tpl && fields.map((f) => (
              <div key={f}>
                <label>{f.replace(/_/g, " ")}</label>
                <input
                  value={values[f] ?? ""}
                  onChange={(e) => setValues({ ...values, [f]: e.target.value })}
                />
              </div>
            ))}
            {missing.length > 0 && (
              <p className="error" style={{ marginTop: 10 }}>
                {missing.length} missing field{missing.length > 1 ? "s" : ""}:{" "}
                {missing.map((m) => m.replace(/_/g, " ")).join(", ")}
              </p>
            )}
            <div style={{ marginTop: 10 }}>
              <button onClick={create} disabled={!tplKey}>Generate</button>
            </div>
          </div>
          <div style={{ flex: 1.4, minWidth: 300 }}>
            <label>Live preview</label>
            {tpl ? (
              <div className="paper-sheet" style={{ fontSize: 13, padding: "24px 28px" }}>
                {renderPreview(tpl.body, values)}
              </div>
            ) : (
              <p className="muted">Pick a template.</p>
            )}
          </div>
        </div>
      </div>

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Documents</h3>
          {docs.length === 0 && <p className="muted">None yet.</p>}
          <div className="doc-grid">
            {docs.map((d) => (
              <button
                key={d.id}
                className={`doc-card ${selected?.id === d.id ? "selected" : ""}`}
                onClick={() => api.getDocument(d.id).then(setSelected)}
              >
                <span className="doc-tag">{d.type.replace(/_/g, " ")}</span>
                <span className="doc-title">{d.title}</span>
                <span className="doc-meta">
                  <span className={`badge ${d.status}`}>{d.status}</span> v{d.current_version}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="card" style={{ flex: 2 }}>
          <h3>Preview</h3>
          {!selected ? (
            <p className="muted">Select a document.</p>
          ) : (
            <>
              <p>
                <strong>{selected.title}</strong>{" "}
                <span className={`badge ${selected.status}`}>{selected.status}</span>{" "}
                <button
                  className="secondary"
                  onClick={() => api.downloadDocumentPdf(selected.id, selected.title)}
                >
                  Download PDF
                </button>
              </p>
              <div className="paper-sheet" style={{ marginBottom: 12 }}>{selected.content}</div>
              {selected.status !== "signed" && (
                <button onClick={requestSignature}>Request &amp; complete e-signature</button>
              )}
              {selected.status === "signed" && (
                <p className="muted">Signed — tamper-evident copy retained.</p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

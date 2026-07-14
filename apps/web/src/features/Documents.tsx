import { useEffect, useState } from "react";
import { api, type Document, type DocTemplate } from "../api";

export default function Documents({ entityId }: { entityId: string }) {
  const [templates, setTemplates] = useState<DocTemplate[]>([]);
  const [docs, setDocs] = useState<Document[]>([]);
  const [selected, setSelected] = useState<Document | null>(null);
  const [tplKey, setTplKey] = useState("");
  const [data, setData] = useState("{}");
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
    let parsed: object;
    try {
      parsed = JSON.parse(data || "{}");
    } catch {
      setError("Data must be valid JSON");
      return;
    }
    try {
      const doc = await api.createDocument(entityId, { template_key: tplKey, data: parsed });
      setSelected(doc);
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

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
          <div>
            <label>Template</label>
            <select value={tplKey} onChange={(e) => setTplKey(e.target.value)}>
              {templates.map((t) => (
                <option key={t.key} value={t.key}>{t.name}</option>
              ))}
            </select>
          </div>
        </div>
        <label>Merge data (JSON)</label>
        <textarea
          rows={4}
          value={data}
          onChange={(e) => setData(e.target.value)}
          style={{ fontFamily: "monospace" }}
          placeholder='{"company": "Acme Pvt Ltd"}'
        />
        <div style={{ marginTop: 10 }}>
          <button onClick={create} disabled={!tplKey}>Generate</button>
        </div>
      </div>

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Documents</h3>
          {docs.length === 0 && <p className="muted">None yet.</p>}
          {docs.map((d) => (
            <div
              key={d.id}
              className={`list-item ${selected?.id === d.id ? "selected" : ""}`}
              onClick={() => api.getDocument(d.id).then(setSelected)}
            >
              {d.title} <span className={`badge ${d.status}`}>{d.status}</span>{" "}
              <span className="muted">v{d.current_version}</span>
            </div>
          ))}
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
              <pre>{selected.content}</pre>
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

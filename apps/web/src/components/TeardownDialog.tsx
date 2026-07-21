import { useEffect, useState } from "react";
import { api, type TeardownPreview } from "../api";

/** Guarded destructive teardown of an entity or a whole workspace. Shows a
 * dry-run breakdown of what will be deleted and requires the user to type the
 * exact name before the delete button unlocks. */
export default function TeardownDialog({
  kind,
  id,
  name,
  onClose,
  onDone,
}: {
  kind: "entity" | "workspace";
  id: string;
  name: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [preview, setPreview] = useState<TeardownPreview | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = kind === "entity" ? api.entityTeardownPreview(id) : api.workspaceTeardownPreview(id);
    load.then(setPreview).catch((e) => setError((e as Error).message));
  }, [kind, id]);

  const noun = kind === "entity" ? "entity" : "workspace";
  const confirmed = typed.trim() === name;

  async function run() {
    setBusy(true);
    setError("");
    try {
      if (kind === "entity") await api.entityTeardown(id, typed.trim());
      else await api.workspaceTeardown(id, typed.trim());
      onDone();
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  }

  const entries = preview ? Object.entries(preview.breakdown) : [];

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-box" onClick={(e) => e.stopPropagation()} style={{ maxWidth: 460 }}>
        <h3 style={{ margin: "0 0 6px", color: "var(--danger, #b91c1c)" }}>
          Delete {noun} — permanent
        </h3>
        <p className="muted" style={{ marginTop: 0 }}>
          This deletes <strong>{name}</strong> and everything inside it. This cannot be undone.
        </p>

        {error && <p className="error">{error}</p>}

        {!preview && !error && <p className="muted">Checking what will be removed…</p>}

        {preview && (
          <>
            {entries.length === 0 ? (
              <p className="muted">No associated records — only the {noun} itself will be removed.</p>
            ) : (
              <div className="card" style={{ margin: "8px 0", maxHeight: 220, overflowY: "auto" }}>
                <p style={{ margin: "0 0 6px", fontWeight: 600 }}>
                  {preview.associated_records} associated record
                  {preview.associated_records === 1 ? "" : "s"} will be deleted:
                </p>
                <table>
                  <tbody>
                    {entries.map(([label, n]) => (
                      <tr key={label}>
                        <td>{label}</td>
                        <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{n}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            <label>
              Type <strong>{name}</strong> to confirm
            </label>
            <input
              autoFocus
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && confirmed && !busy) run();
                if (e.key === "Escape") onClose();
              }}
              placeholder={name}
            />
          </>
        )}

        <div className="row" style={{ justifyContent: "flex-end", gap: 8, marginTop: 14 }}>
          <button className="secondary" style={{ flex: "0 0 auto" }} onClick={onClose}>
            Cancel
          </button>
          <button
            style={{
              flex: "0 0 auto",
              background: "var(--danger, #b91c1c)",
              borderColor: "var(--danger, #b91c1c)",
              opacity: confirmed && !busy ? 1 : 0.5,
            }}
            disabled={!confirmed || busy}
            onClick={run}
          >
            {busy ? "Deleting…" : `Delete ${noun}`}
          </button>
        </div>
      </div>
    </div>
  );
}

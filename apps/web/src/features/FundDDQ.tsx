import { Fragment, useEffect, useState } from "react";
import { api, type DDQList } from "../api";
import { useGuard } from "../hooks";

/** DDQ answer bank (Visible-style): answer LP due-diligence questions once,
 * reuse them for every questionnaire, and export the lot as a document. */
export default function FundDDQ({ fundId }: { fundId: string }) {
  const [ddq, setDdq] = useState<DDQList | null>(null);
  const [category, setCategory] = useState("");
  const [question, setQuestion] = useState("");
  const [reg, setReg] = useState("none");
  const [editing, setEditing] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const { error, guard } = useGuard(() => load());

  const load = () => api.listDdq(fundId).then(setDdq);
  useEffect(() => {
    load();
  }, [fundId]);

  if (!ddq) return null;
  const answered = ddq.entries.filter((e) => e.answered).length;
  const groups: Record<string, typeof ddq.entries> = {};
  for (const e of ddq.entries) (groups[e.category] ??= []).push(e);
  const unusedPresets = ddq.presets.filter(
    (p) => !ddq.entries.some((e) => e.question === p.question)
  );

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>🗂️</span> DDQ answer bank
        {ddq.entries.length > 0 && (
          <span className="badge">{answered} / {ddq.entries.length} answered</span>
        )}
        <button
          className="secondary"
          style={{ marginLeft: "auto" }}
          disabled={ddq.entries.length === 0}
          onClick={guard(async () => {
            await api.ddqReport(fundId);
          }, "DDQ responses document generated — see the Documents tab")}
        >
          Generate DDQ document
        </button>
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Answer LP due-diligence questions once and reuse them for every questionnaire — export
        the whole bank as a document when an LP sends a DDQ.
      </p>
      {error && <p className="error">{error}</p>}

      {Object.entries(groups).map(([cat, entries]) => (
        <div key={cat} style={{ marginBottom: 10 }}>
          <div className="muted" style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 4 }}>
            {cat}
          </div>
          {entries.map((e) => (
            <Fragment key={e.id}>
              <div style={{ display: "flex", alignItems: "baseline", gap: 8, padding: "4px 0", borderTop: "1px solid var(--border)" }}>
                <span style={{ flex: 1 }}>
                  <strong>{e.question}</strong>
                  {e.regulator !== "none" && (
                    <span className="badge" style={{ marginLeft: 6 }}>{e.regulator.toUpperCase()}</span>
                  )}
                  <div className="muted">
                    {e.answered ? e.answer : <em>No answer yet</em>}
                    {(e.assignee || e.reviewer) && (
                      <span> · {e.assignee ? `owner ${e.assignee}` : ""}{e.reviewer ? ` · reviewer ${e.reviewer}` : ""}</span>
                    )}
                  </div>
                </span>
                <select
                  value={e.status}
                  title="Workflow status"
                  style={{ flex: "0 0 auto", maxWidth: 120 }}
                  onChange={(ev) => {
                    const v = ev.target.value;
                    guard(async () => {
                      await api.updateDdqEntry(fundId, e.id, { status: v });
                    })();
                  }}
                >
                  <option value="draft">draft</option>
                  <option value="in_review">in review</option>
                  <option value="approved">approved</option>
                </select>
                <button
                  className="secondary"
                  style={{ flex: "0 0 auto" }}
                  onClick={() => {
                    setEditing(editing === e.id ? null : e.id);
                    setDraft(e.answer ?? "");
                  }}
                >
                  {e.answered ? "Edit" : "Answer"}
                </button>
                <button
                  className="secondary"
                  style={{ flex: "0 0 auto" }}
                  title="Remove this question"
                  onClick={guard(async () => {
                    await api.deleteDdqEntry(fundId, e.id);
                  }, "Question removed")}
                >
                  ×
                </button>
              </div>
              {editing === e.id && (
                <div style={{ display: "flex", gap: 8, alignItems: "flex-end", margin: "4px 0 8px" }}>
                  <textarea
                    rows={2}
                    style={{ flex: 1 }}
                    value={draft}
                    onChange={(ev) => setDraft(ev.target.value)}
                  />
                  <button
                    style={{ flex: "0 0 auto" }}
                    onClick={guard(async () => {
                      await api.updateDdqEntry(fundId, e.id, { answer: draft || null });
                      setEditing(null);
                    }, "Answer saved")}
                  >
                    Save
                  </button>
                </div>
              )}
            </Fragment>
          ))}
        </div>
      ))}

      <div className="row" style={{ alignItems: "flex-end", marginTop: 8 }}>
        <div style={{ flex: 2 }}>
          <label>New question</label>
          <input value={question} onChange={(e) => setQuestion(e.target.value)} />
        </div>
        <div style={{ flex: 1 }}>
          <label>Category</label>
          <input placeholder="General" value={category} onChange={(e) => setCategory(e.target.value)} />
        </div>
        <div style={{ flex: "0 0 auto" }}>
          <label>Regulator</label>
          <select value={reg} onChange={(e) => setReg(e.target.value)}>
            <option value="none">—</option>
            <option value="sec">SEC</option>
            <option value="sebi">SEBI</option>
          </select>
        </div>
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!question.trim()}
          onClick={guard(async () => {
            await api.addDdqEntry(fundId, { question, category: category || null, regulator: reg });
            setQuestion("");
          }, "Question added")}
        >
          Add question
        </button>
      </div>
      {unusedPresets.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 8, alignItems: "center" }}>
          <span className="muted" style={{ fontSize: 12 }}>Standard questions:</span>
          {unusedPresets.map((p) => (
            <button
              key={p.question}
              className="secondary"
              title={p.question}
              onClick={guard(async () => {
                await api.addDdqEntry(fundId, p);
              }, "Question added")}
            >
              + {p.question.length > 48 ? `${p.question.slice(0, 48)}…` : p.question}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

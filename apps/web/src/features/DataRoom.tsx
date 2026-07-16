import { useEffect, useState } from "react";
import { uiPrompt } from "../components/Prompt";
import { useGuard } from "../hooks";
import {
  api,
  type DataRoom as DataRoomT,
  type DataRoomQuestion,
  type Document,
  type Engagement,
} from "../api";
import EmptyState from "../components/EmptyState";

export default function DataRoom({ entityId }: { entityId: string }) {
  const [rooms, setRooms] = useState<DataRoomT[]>([]);
  const [selected, setSelected] = useState<DataRoomT | null>(null);
  const [docs, setDocs] = useState<Document[]>([]);
  const [engagement, setEngagement] = useState<Engagement[]>([]);
  const [questions, setQuestions] = useState<DataRoomQuestion[]>([]);
  const [qText, setQText] = useState("");
  const [preview, setPreview] = useState<Document | null>(null);
  const [name, setName] = useState("Diligence room");
  const [docId, setDocId] = useState("");
  const [email, setEmail] = useState("");
  const { error, setError, guard } = useGuard();

  async function load() {
    try {
      const [r, d] = await Promise.all([api.listDataRooms(entityId), api.listDocuments(entityId)]);
      setRooms(r);
      setDocs(d);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  async function select(id: string) {
    setPreview(null);
    setSelected(await api.getDataRoom(id));
    setEngagement(await api.engagement(id));
    setQuestions(await api.listQuestions(id));
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>Create data room</h2>
        <div className="row">
          <input value={name} onChange={(e) => setName(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            onClick={guard(async () => {
              const room = await api.createDataRoom(entityId, { name });
              await load();
              await select(room.id);
            })}
          >
            Create
          </button>
        </div>
      </div>

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Rooms</h3>
          {rooms.length === 0 && (
            <EmptyState icon="🗂️" title="No data rooms yet" hint="Create a room to share documents with investors for diligence, with per-email access and expiry." />
          )}
          {rooms.map((r) => (
            <div
              key={r.id}
              className={`list-item ${selected?.id === r.id ? "selected" : ""}`}
              onClick={() => select(r.id)}
            >
              {r.name} <span className="badge">{r.scope}</span>
            </div>
          ))}
        </div>

        <div className="card" style={{ flex: 2 }}>
          {!selected ? (
            <p className="muted">Select a room.</p>
          ) : (
            <>
              <h3>{selected.name}</h3>

              <div className="row">
                <select value={docId} onChange={(e) => setDocId(e.target.value)}>
                  <option value="">— add a document —</option>
                  {docs.map((d) => (
                    <option key={d.id} value={d.id}>{d.title}</option>
                  ))}
                </select>
                <button
                  style={{ flex: "0 0 auto" }}
                  disabled={!docId}
                  onClick={guard(async () => {
                    await api.addDataRoomItem(selected.id, { document_id: docId });
                    setDocId("");
                    await select(selected.id);
                  })}
                >
                  Add item
                </button>
              </div>

              <table style={{ marginTop: 10 }}>
                <thead>
                  <tr>
                    <th>Document</th>
                    <th>Folder</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {selected.items.map((i) => (
                    <tr key={i.id}>
                      <td>{i.document_title}</td>
                      <td>{i.folder}</td>
                      <td>
                        <button
                          className="secondary"
                          onClick={guard(async () => {
                            setPreview(await api.viewItem(selected.id, i.id));
                            setEngagement(await api.engagement(selected.id));
                          })}
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div className="row" style={{ marginTop: 12 }}>
                <input
                  placeholder="investor@vc.in"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <button
                  style={{ flex: "0 0 auto" }}
                  disabled={!email}
                  onClick={guard(async () => {
                    await api.addGrant(selected.id, { email });
                    setEmail("");
                    await select(selected.id);
                  })}
                >
                  Grant access
                </button>
              </div>
              <p className="muted">
                Access: {selected.grants.map((g) => g.email).join(", ") || "none"}
              </p>

              {engagement.length > 0 && (
                <>
                  <h3>Engagement</h3>
                  <table>
                    <thead>
                      <tr>
                        <th>Actor</th>
                        <th>Document</th>
                        <th>Views</th>
                      </tr>
                    </thead>
                    <tbody>
                      {engagement.map((e, i) => (
                        <tr key={i}>
                          <td>{e.actor}</td>
                          <td className="muted">{e.document_id}</td>
                          <td>{e.views}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </>
              )}

              <h3>Diligence Q&amp;A</h3>
              <div className="row">
                <input placeholder="Ask a question…" value={qText} onChange={(e) => setQText(e.target.value)} />
                <button
                  style={{ flex: "0 0 auto" }}
                  disabled={!qText}
                  onClick={guard(async () => {
                    await api.askQuestion(selected.id, { question: qText });
                    setQText("");
                    setQuestions(await api.listQuestions(selected.id));
                  })}
                >
                  Ask
                </button>
              </div>
              {questions.map((q) => (
                <div key={q.id} style={{ borderTop: "1px solid var(--border)", padding: "8px 0" }}>
                  <div><strong>Q:</strong> {q.question} <span className="muted">— {q.asker}</span></div>
                  {q.answer ? (
                    <div><strong>A:</strong> {q.answer} <span className="muted">— {q.answered_by}</span></div>
                  ) : (
                    <button
                      className="secondary"
                      onClick={guard(async () => {
                        const a = await uiPrompt("Answer:");
                        if (a) {
                          await api.answerQuestion(q.id, { answer: a });
                          setQuestions(await api.listQuestions(selected.id));
                        }
                      })}
                    >
                      Answer
                    </button>
                  )}
                </div>
              ))}

              {preview && (
                <>
                  <h3>Preview: {preview.title}</h3>
                  <pre>{preview.content}</pre>
                </>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

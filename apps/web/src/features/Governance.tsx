import { Fragment, useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { uiPrompt } from "../components/Prompt";
import { useGuard } from "../hooks";
import { api, type AttendeesView, type Director, type Meeting, type Resolution, type VoteTally } from "../api";

const RES_TYPES = ["board", "ordinary", "special", "circular"];
const DESIGNATIONS = [
  "director",
  "managing_director",
  "whole_time_director",
  "independent_director",
  "nominee_director",
  "company_secretary",
  "cfo",
];

export default function Governance({ entityId }: { entityId: string }) {
  const [meetings, setMeetings] = useState<Meeting[]>([]);
  const [resolutions, setResolutions] = useState<Resolution[]>([]);
  const [directors, setDirectors] = useState<Director[]>([]);
  const [agendaText, setAgendaText] = useState<Record<string, string>>({});
  const [note, setNote] = useState("");
  const { error, setError, guard } = useGuard(() => load());

  // director form
  const [dName, setDName] = useState("");
  const [dDin, setDDin] = useState("");
  const [dDesig, setDDesig] = useState("director");

  // forms
  const [mType, setMType] = useState("board");
  const [mTitle, setMTitle] = useState("");
  const [mDate, setMDate] = useState("2026-04-15");
  const [rType, setRType] = useState("board");
  const [rMeeting, setRMeeting] = useState("");
  const [rTitle, setRTitle] = useState("");
  const [rText, setRText] = useState("");

  async function load() {
    try {
      const [m, r, d] = await Promise.all([
        api.listMeetings(entityId),
        api.listResolutions(entityId),
        api.listDirectors(entityId),
      ]);
      setMeetings(m);
      setResolutions(r);
      setDirectors(d);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  return (
    <div>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Schedule meeting</h3>
          <label>Type</label>
          <select value={mType} onChange={(e) => setMType(e.target.value)}>
            <option value="board">Board</option>
            <option value="agm">AGM</option>
            <option value="egm">EGM</option>
          </select>
          <label>Title</label>
          <input value={mTitle} onChange={(e) => setMTitle(e.target.value)} />
          <label>Date</label>
          <input type="date" value={mDate} onChange={(e) => setMDate(e.target.value)} />
          <div style={{ marginTop: 10 }}>
            <button
              disabled={!mTitle}
              onClick={guard(async () => {
                await api.createMeeting(entityId, { type: mType, title: mTitle, date: mDate });
                setMTitle("");
              })}
            >
              Schedule
            </button>
          </div>
        </div>

        <div className="card" style={{ flex: 2 }}>
          <h3>Meetings</h3>
          {meetings.length === 0 && (
            <EmptyState icon="🗓️" title="No meetings yet" hint="Schedule a board meeting, AGM or EGM on the left — add agenda items and generate the notice." />
          )}
          {meetings.map((m) => (
            <div key={m.id} className="list-item" style={{ cursor: "default" }}>
              <strong>{m.title}</strong> <span className="badge">{m.type}</span>{" "}
              <span className={`badge ${m.status === "held" ? "complete" : ""}`}>{m.status}</span>{" "}
              <span className="muted">{m.date}</span>
              {m.agenda_items.length > 0 && (
                <ol className="muted" style={{ margin: "6px 0" }}>
                  {m.agenda_items.map((a) => <li key={a.id}>{a.title}</li>)}
                </ol>
              )}
              <MeetingAttendees meetingId={m.id} />
              <div className="row" style={{ marginTop: 6 }}>
                <input
                  placeholder="Agenda item"
                  value={agendaText[m.id] ?? ""}
                  onChange={(e) => setAgendaText({ ...agendaText, [m.id]: e.target.value })}
                />
                <button
                  className="secondary"
                  style={{ flex: "0 0 auto" }}
                  disabled={!agendaText[m.id]}
                  onClick={guard(async () => {
                    await api.addAgendaItem(m.id, {
                      title: agendaText[m.id],
                      order_index: m.agenda_items.length + 1,
                    });
                    setAgendaText({ ...agendaText, [m.id]: "" });
                  })}
                >
                  Add agenda
                </button>
                <button
                  className="secondary"
                  style={{ flex: "0 0 auto" }}
                  onClick={guard(async () => {
                    await api.generateNotice(m.id);
                    setNote("Meeting notice generated (see Files / Documents).");
                  })}
                >
                  {m.notice_document_id ? "Notice ✓ (regenerate)" : "Generate notice"}
                </button>
                {m.status !== "held" && (
                  <button
                    className="secondary"
                    style={{ flex: "0 0 auto" }}
                    onClick={guard(() =>
                      api.recordMinutes(m.id, { minutes: "Quorum present; resolutions passed.", status: "held" })
                    )}
                  >
                    Record minutes
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h3>Directors &amp; KMP register</h3>
        <div className="row">
          <input placeholder="Name" value={dName} onChange={(e) => setDName(e.target.value)} />
          <input placeholder="DIN" value={dDin} onChange={(e) => setDDin(e.target.value)} />
          <select value={dDesig} onChange={(e) => setDDesig(e.target.value)}>
            {DESIGNATIONS.map((x) => <option key={x} value={x}>{x.replace(/_/g, " ")}</option>)}
          </select>
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!dName}
            onClick={guard(async () => {
              await api.appointDirector(entityId, {
                name: dName,
                din: dDin || null,
                designation: dDesig,
                appointed_on: new Date().toISOString().slice(0, 10),
              });
              setDName(""); setDDin("");
            })}
          >
            Appoint
          </button>
        </div>
        {directors.length > 0 && (
          <table style={{ marginTop: 10 }}>
            <thead>
              <tr><th>Name</th><th>DIN</th><th>Designation</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {directors.map((d) => (
                <tr key={d.id}>
                  <td>{d.name}</td>
                  <td>{d.din || "—"}</td>
                  <td>{d.designation.replace(/_/g, " ")}</td>
                  <td><span className={`badge ${d.status === "active" ? "complete" : "skipped"}`}>{d.status}</span></td>
                  <td>
                    <button className="secondary" onClick={guard(() => api.indemnifyDirector(d.id))}>
                      D&amp;O indemnity
                    </button>{" "}
                    {d.status === "active" && (
                      <button
                        className="secondary"
                        onClick={guard(() => api.resignDirector(d.id, { resigned_on: new Date().toISOString().slice(0, 10) }))}
                      >
                        Resign
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Propose resolution</h3>
        <div className="row">
          <div>
            <label>Type</label>
            <select value={rType} onChange={(e) => setRType(e.target.value)}>
              {RES_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div>
            <label>Meeting (optional)</label>
            <select value={rMeeting} onChange={(e) => setRMeeting(e.target.value)}>
              <option value="">— circular / none —</option>
              {meetings.map((m) => <option key={m.id} value={m.id}>{m.title}</option>)}
            </select>
          </div>
        </div>
        <label>Title</label>
        <input value={rTitle} onChange={(e) => setRTitle(e.target.value)} />
        <label>Text</label>
        <input value={rText} onChange={(e) => setRText(e.target.value)} placeholder="RESOLVED THAT ..." />
        <div style={{ marginTop: 10 }}>
          <button
            disabled={!rTitle || !rText}
            onClick={guard(async () => {
              await api.createResolution(entityId, {
                type: rType,
                meeting_id: rMeeting || null,
                title: rTitle,
                text: rText,
              });
              setRTitle(""); setRText("");
            })}
          >
            Propose
          </button>{" "}
          <button
            className="secondary"
            title="Alter the MoA or AoA — creates a special resolution + document; MGT-14 is filed on passing"
            onClick={guard(async () => {
              const kind = await uiPrompt("Amend which charter document? (moa / aoa)", "aoa");
              if (!kind || !["moa", "aoa"].includes(kind.toLowerCase())) return;
              const description = await uiPrompt("Describe the alteration:");
              if (!description) return;
              await api.charterAmendment(entityId, { kind: kind.toLowerCase(), description });
              setNote(
                "Charter amendment drafted: special resolution + document created. Passing the resolution adds the MGT-14 filing to Compliance."
              );
            }, "Charter amendment drafted")}
          >
            Amend charter (MoA/AoA)
          </button>
        </div>
      </div>

      <div className="card">
        <h3>Resolutions</h3>
        {resolutions.length === 0 ? (
          <EmptyState icon="📜" title="No resolutions yet" hint="Propose a board, ordinary or special resolution above — pass it to generate the document and any linked filing." />
        ) : (
          <table>
            <thead>
              <tr><th>Title</th><th>Type</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {resolutions.map((r) => (
                <Fragment key={r.id}>
                <tr>
                  <td>{r.title}</td>
                  <td>{r.type}</td>
                  <td><span className={`badge ${r.status === "passed" ? "complete" : ""}`}>{r.status}</span></td>
                  <td>
                    {r.status === "draft" && (
                      <button
                        className="secondary"
                        onClick={guard(() => api.setResolutionStatus(r.id, { status: "passed" }))}
                      >
                        Pass
                      </button>
                    )}{" "}
                    {r.document_id ? (
                      <span className="muted">doc ✓</span>
                    ) : (
                      <button
                        className="secondary"
                        onClick={guard(async () => {
                          await api.generateResolutionDoc(r.id);
                          setNote("Resolution document generated (see Documents tab).");
                        })}
                      >
                        Generate doc
                      </button>
                    )}{" "}
                    <button
                      className="secondary"
                      onClick={guard(async () => {
                        const res = await api.requestConsents(r.id);
                        const t = (await api.listConsents(r.id)).tally;
                        setNote(
                          `Consents — requested from ${res.total} investor(s): ` +
                            `${t.approved} approved · ${t.rejected} rejected · ${t.pending} pending.`
                        );
                      })}
                    >
                      Investor consents
                    </button>
                  </td>
                </tr>
                <tr>
                  <td colSpan={4} style={{ background: "var(--surface-2, #f6f7f5)" }}>
                    <ResolutionVotes resolutionId={r.id} />
                  </td>
                </tr>
                </Fragment>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

/** Attendee list + quorum for one meeting (record who was present). */
function MeetingAttendees({ meetingId }: { meetingId: string }) {
  const [data, setData] = useState<AttendeesView | null>(null);
  const [name, setName] = useState("");
  const [role, setRole] = useState("director");
  const [present, setPresent] = useState(true);
  useEffect(() => {
    api.listAttendees(meetingId).then(setData).catch(() => {});
  }, [meetingId]);
  const quorumNote =
    data && data.quorum != null
      ? ` · ${data.present}/${data.quorum} for quorum ${data.quorum_met ? "✓" : "✗"}`
      : data
        ? ` · ${data.present} present`
        : "";
  return (
    <div style={{ marginTop: 6 }}>
      <div className="muted" style={{ fontSize: 12 }}>Attendees{quorumNote}</div>
      {data?.attendees.map((a) => (
        <span key={a.id} className="badge" style={{ marginRight: 4 }}>
          {a.name}{a.present ? "" : " (absent)"}
        </span>
      ))}
      <div className="row" style={{ marginTop: 4 }}>
        <input placeholder="Attendee name" value={name} onChange={(e) => setName(e.target.value)} />
        <select value={role} onChange={(e) => setRole(e.target.value)} style={{ maxWidth: 140 }}>
          <option value="director">director</option>
          <option value="shareholder">shareholder</option>
          <option value="invitee">invitee</option>
        </select>
        <label style={{ display: "flex", alignItems: "center", gap: 4, flex: "0 0 auto" }}>
          <input type="checkbox" checked={present} onChange={(e) => setPresent(e.target.checked)} /> present
        </label>
        <button
          className="secondary"
          style={{ flex: "0 0 auto" }}
          disabled={!name}
          onClick={async () => {
            setData(await api.addAttendee(meetingId, { name, role, present }));
            setName("");
          }}
        >
          Add
        </button>
      </div>
    </div>
  );
}

/** For/against/abstain voting on one resolution, with a running tally. */
function ResolutionVotes({ resolutionId }: { resolutionId: string }) {
  const [tally, setTally] = useState<VoteTally | null>(null);
  const [voter, setVoter] = useState("");
  const [vote, setVote] = useState("for");
  useEffect(() => {
    api.listVotes(resolutionId).then((r) => setTally(r.tally)).catch(() => {});
  }, [resolutionId]);
  return (
    <div>
      <span className="muted" style={{ fontSize: 12 }}>
        Votes:{" "}
        {tally && tally.total > 0
          ? `For ${tally.for} · Against ${tally.against} · Abstain ${tally.abstain}`
          : "none recorded"}
      </span>
      <div className="row" style={{ marginTop: 4 }}>
        <input placeholder="Voter" value={voter} onChange={(e) => setVoter(e.target.value)} />
        <select value={vote} onChange={(e) => setVote(e.target.value)} style={{ maxWidth: 120 }}>
          <option value="for">for</option>
          <option value="against">against</option>
          <option value="abstain">abstain</option>
        </select>
        <button
          className="secondary"
          style={{ flex: "0 0 auto" }}
          disabled={!voter}
          onClick={async () => {
            const r = await api.recordVote(resolutionId, { voter, vote });
            setTally(r.tally);
            setVoter("");
          }}
        >
          Vote
        </button>
      </div>
    </div>
  );
}

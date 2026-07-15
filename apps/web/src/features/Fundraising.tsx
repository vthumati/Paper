import { useEffect, useState } from "react";
import KindBadge from "../components/KindBadge";
import { useGuard } from "../hooks";
import {
  api,
  type DataRoom,
  type FunnelView,
  type Round,
  type RoundCommitment,
  type RoundSummary,
  type SecurityClass,
} from "../api";

const STATUSES = ["soft", "signed", "funded"];

export default function Fundraising({ entityId }: { entityId: string }) {
  const [rounds, setRounds] = useState<Round[]>([]);
  const [classes, setClasses] = useState<SecurityClass[]>([]);
  const [selected, setSelected] = useState<Round | null>(null);
  const [summary, setSummary] = useState<RoundSummary | null>(null);
  const [commitments, setCommitments] = useState<RoundCommitment[]>([]);
  const [funnel, setFunnel] = useState<FunnelView | null>(null);
  const [rooms, setRooms] = useState<DataRoom[]>([]);
  const [funnelRoom, setFunnelRoom] = useState("");
  const [note, setNote] = useState("");
  const { error, setError, guard } = useGuard(async () => {
    await load();
    if (selected) await select(selected.id);
  });

  // forms
  const [name, setName] = useState("Seed");
  const [pre, setPre] = useState("40000000");
  const [target, setTarget] = useState("10000000");
  const [pps, setPps] = useState("100");
  const [scId, setScId] = useState("");
  const [invName, setInvName] = useState("");
  const [invAmt, setInvAmt] = useState("");
  const [invKind, setInvKind] = useState("institutional");
  const [invForeign, setInvForeign] = useState(false);

  async function load() {
    try {
      const [r, c] = await Promise.all([
        api.listRounds(entityId),
        api.listSecurityClasses(entityId),
      ]);
      setRounds(r);
      setClasses(c);
      if (!scId && c.length) setScId(c[0].id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  async function select(rid: string) {
    setNote("");
    const [s, c, f, dr] = await Promise.all([
      api.roundSummary(rid),
      api.listCommitments(rid),
      api.getFunnel(entityId, rid),
      api.listDataRooms(entityId),
    ]);
    setSummary(s);
    setCommitments(c);
    setFunnel(f);
    setRooms(dr);
    setSelected(rounds.find((r) => r.id === rid) ?? null);
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      <div className="card">
        <h3>Open a round</h3>
        <div className="row">
          <div><label>Name</label><input value={name} onChange={(e) => setName(e.target.value)} /></div>
          <div><label>Pre-money (₹)</label><input value={pre} onChange={(e) => setPre(e.target.value)} /></div>
          <div><label>Target (₹)</label><input value={target} onChange={(e) => setTarget(e.target.value)} /></div>
          <div><label>Price/share (₹)</label><input value={pps} onChange={(e) => setPps(e.target.value)} /></div>
          <div>
            <label>Security class</label>
            <select value={scId} onChange={(e) => setScId(e.target.value)}>
              <option value="">—</option>
              {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </div>
        </div>
        <div style={{ marginTop: 10 }}>
          <button
            disabled={!name || !scId}
            onClick={guard(() =>
              api.createRound(entityId, {
                name,
                instrument: "ccps",
                pre_money: pre,
                target_amount: target,
                price_per_share: pps,
                security_class_id: scId,
              })
            )}
          >
            Create round
          </button>
        </div>
      </div>

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Rounds</h3>
          {rounds.length === 0 && <p className="muted">None yet.</p>}
          {rounds.map((r) => (
            <div
              key={r.id}
              className={`list-item ${selected?.id === r.id ? "selected" : ""}`}
              onClick={() => select(r.id)}
            >
              {r.name} <span className={`badge ${r.status === "closed" ? "complete" : ""}`}>{r.status}</span>
            </div>
          ))}
        </div>

        <div className="card" style={{ flex: 2 }}>
          {!selected || !summary ? (
            <p className="muted">Select a round.</p>
          ) : (
            <>
              <h3>{selected.name}</h3>
              <p className="muted">
                Pre ₹{summary.pre_money} · Committed ₹{summary.committed} · Post ₹{summary.post_money} ·
                New shares {summary.new_shares.toLocaleString()} ({summary.implied_new_ownership_pct}% to
                new investors)
              </p>

              {selected.status !== "closed" && (
                <>
                  <div className="row">
                    <input placeholder="Investor" value={invName} onChange={(e) => setInvName(e.target.value)} />
                    <select value={invKind} onChange={(e) => setInvKind(e.target.value)} style={{ flex: "0 0 auto", width: "auto" }}>
                      <option value="institutional">Institutional</option>
                      <option value="angel">Angel</option>
                      <option value="friend_family">Friends &amp; family</option>
                    </select>
                    <input placeholder="Amount ₹" value={invAmt} onChange={(e) => setInvAmt(e.target.value)} />
                    <label style={{ flex: "0 0 auto", display: "flex", alignItems: "center", gap: 4 }}>
                      <input type="checkbox" style={{ width: "auto" }} checked={invForeign} onChange={(e) => setInvForeign(e.target.checked)} />
                      foreign
                    </label>
                    <button
                      style={{ flex: "0 0 auto" }}
                      disabled={!invName || !invAmt}
                      onClick={guard(async () => {
                        await api.addCommitment(selected.id, { investor_name: invName, investor_kind: invKind, amount: invAmt, is_foreign: invForeign });
                        setInvName(""); setInvAmt(""); setInvForeign(false);
                      })}
                    >
                      Add commitment
                    </button>
                  </div>
                </>
              )}

              <table style={{ marginTop: 10 }}>
                <thead>
                  <tr><th>Investor</th><th>Kind</th><th>Amount</th><th>Foreign</th><th>Status</th><th></th></tr>
                </thead>
                <tbody>
                  {commitments.map((c) => (
                    <tr key={c.id}>
                      <td>{c.investor_name}</td>
                      <td><KindBadge kind={c.investor_kind} /></td>
                      <td>₹{c.amount}</td>
                      <td>{c.is_foreign ? "yes" : "—"}</td>
                      <td>
                        {selected.status === "closed" ? (
                          <span className="badge">{c.status}</span>
                        ) : (
                          <select
                            value={c.status}
                            onChange={(ev) => guard(() => api.updateCommitment(selected.id, c.id, { status: ev.target.value }))()}
                          >
                            {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                          </select>
                        )}
                      </td>
                      <td>
                        <button
                          className="secondary"
                          title="PAS-4 private placement offer letter (Sec 42)"
                          onClick={guard(async () => {
                            await api.generateOfferLetter(selected.id, c.id);
                            setNote(`PAS-4 offer letter generated for ${c.investor_name} (see Documents tab).`);
                          })}
                        >
                          PAS-4
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>

              <div style={{ marginTop: 12 }} className="row">
                <button
                  className="secondary"
                  style={{ flex: "0 0 auto" }}
                  onClick={guard(async () => {
                    await api.generateTermSheet(selected.id);
                    setNote("Term sheet generated (see Documents tab).");
                  })}
                >
                  Generate term sheet
                </button>
                {selected.status !== "closed" && (
                  <button
                    style={{ flex: "0 0 auto" }}
                    onClick={guard(async () => {
                      const r = await api.closeRound(selected.id);
                      setNote(
                        `Closed: issued ${r.issued} allotment(s)` +
                          (r.instruments_converted
                            ? `; ${r.instruments_converted} SAFE/note(s) converted`
                            : "") +
                          (r.foreign_investors ? "; FC-GPR FEMA filing added to Compliance." : ".")
                      );
                    })}
                  >
                    Close round
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>

      {selected && funnel && (
        <div className="card">
          <h3>Investor funnel</h3>
          {funnel.link && funnel.link.active ? (
            <p className="muted">
              Share this link with prospective investors:{" "}
              <code>{`${window.location.origin}/invest/${funnel.link.token}`}</code>{" "}
              <button
                className="secondary"
                onClick={() =>
                  navigator.clipboard.writeText(
                    `${window.location.origin}/invest/${funnel.link!.token}`
                  )
                }
              >
                Copy
              </button>{" "}
              <button
                className="secondary"
                onClick={guard(() => api.deactivateFunnelLink(entityId, selected.id))}
              >
                Deactivate
              </button>
              {funnel.link.data_room_id && " — opting in grants data-room access automatically."}
            </p>
          ) : (
            <div className="row" style={{ alignItems: "flex-end" }}>
              <div>
                <label>Data room to share (optional)</label>
                <select value={funnelRoom} onChange={(e) => setFunnelRoom(e.target.value)}>
                  <option value="">— none —</option>
                  {rooms.map((r) => (
                    <option key={r.id} value={r.id}>{r.name}</option>
                  ))}
                </select>
              </div>
              <button
                style={{ flex: "0 0 auto" }}
                onClick={guard(() =>
                  api.createFunnelLink(entityId, selected.id, {
                    data_room_id: funnelRoom || null,
                  })
                )}
              >
                Create share link
              </button>
            </div>
          )}

          {funnel.prospects.length > 0 && (
            <table style={{ marginTop: 10 }}>
              <thead>
                <tr>
                  <th>Prospect</th><th>Firm</th><th>Email</th><th>Stage</th>
                  <th>Check size</th><th>Room views</th><th>Commitment</th>
                </tr>
              </thead>
              <tbody>
                {funnel.prospects.map((p) => (
                  <tr key={p.id}>
                    <td>{p.name}</td>
                    <td>{p.firm ?? "—"}</td>
                    <td>{p.email ?? "—"}</td>
                    <td><span className="badge">{p.stage}</span></td>
                    <td>{p.check_size ? `₹${p.check_size}` : "—"}</td>
                    <td>{p.data_room_views}</td>
                    <td>
                      {p.commitment ? (
                        <span className="badge complete">
                          ₹{p.commitment.amount} ({p.commitment.status})
                        </span>
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
      )}
    </div>
  );
}

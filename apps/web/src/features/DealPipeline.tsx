import { Fragment, useEffect, useState } from "react";
import { uiPrompt } from "../components/Prompt";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";
import { api, type Deal, type DealCrm } from "../api";

const STAGES = ["sourced", "screening", "diligence", "ic", "term_sheet", "invested", "passed"];
const ACT_KINDS = ["note", "meeting", "call", "email", "other"];
const todayIso = () => new Date().toISOString().slice(0, 10);

/** GP-side deal flow: sourced → screening → diligence → IC → term sheet → invested,
 * with per-deal relationship intelligence (contacts + a dated activity timeline). */
export default function DealPipeline({
  fundId,
  onInvested,
}: {
  fundId: string;
  onInvested?: () => void;
}) {
  const [deals, setDeals] = useState<Deal[]>([]);
  const { error, setError, guard } = useGuard(() => load());
  const [name, setName] = useState("");
  const [sector, setSector] = useState("");
  const [amount, setAmount] = useState("");

  // expanded deal CRM
  const [openId, setOpenId] = useState<string | null>(null);
  const [crm, setCrm] = useState<DealCrm | null>(null);
  const [cName, setCName] = useState("");
  const [cRole, setCRole] = useState("");
  const [actKind, setActKind] = useState("note");
  const [actBody, setActBody] = useState("");
  const [actDate, setActDate] = useState(todayIso());

  async function load() {
    try {
      setDeals(await api.listDeals(fundId));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [fundId]);

  async function toggle(id: string) {
    if (openId === id) {
      setOpenId(null);
      setCrm(null);
      return;
    }
    setOpenId(id);
    setCrm(null);
    setCrm(await api.dealCrm(id));
  }

  return (
    <div className="card">
      <h3>Deal pipeline</h3>
      {error && <p className="error">{error}</p>}
      <div className="row">
        <input placeholder="Company" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="Sector" value={sector} onChange={(e) => setSector(e.target.value)} />
        <input placeholder="Cheque ₹" value={amount} onChange={(e) => setAmount(e.target.value)} />
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!name}
          onClick={guard(async () => {
            await api.createDeal(fundId, { company_name: name, sector: sector || null, amount: amount || "0" });
            setName(""); setSector(""); setAmount("");
          })}
        >
          Add deal
        </button>
      </div>
      {deals.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Company</th><th>Sector</th><th>Cheque</th><th>Stage</th><th></th><th></th></tr>
          </thead>
          <tbody>
            {deals.map((d) => (
              <Fragment key={d.id}>
                <tr>
                  <td>{d.company_name}</td>
                  <td>{d.sector ?? "—"}</td>
                  <td>{fmtMoney(d.amount)}</td>
                  <td>
                    {d.stage === "invested" ? (
                      <span className="badge complete">invested</span>
                    ) : (
                      <select
                        value={d.stage}
                        onChange={(ev) => guard(() => api.setDealStage(d.id, ev.target.value))()}
                      >
                        {STAGES.filter((s) => s !== "invested").map((s) => (
                          <option key={s} value={s}>{s}</option>
                        ))}
                      </select>
                    )}
                  </td>
                  <td>
                    <button className="secondary" onClick={() => toggle(d.id)}>
                      {openId === d.id ? "Hide" : "CRM"}
                    </button>
                  </td>
                  <td>
                    {d.stage !== "invested" && d.stage !== "passed" && (
                      <button
                        className="secondary"
                        onClick={guard(async () => {
                          const pct = await uiPrompt(`Ownership % acquired in ${d.company_name}:`, "10");
                          await api.investDeal(d.id, { ownership_pct: pct || "0" });
                          onInvested?.();
                        })}
                      >
                        Invest
                      </button>
                    )}
                  </td>
                </tr>
                {openId === d.id && (
                  <tr>
                    <td colSpan={6} style={{ background: "var(--light)" }}>
                      {!crm ? (
                        <span className="muted">Loading…</span>
                      ) : (
                        <div className="row" style={{ alignItems: "flex-start", gap: 20 }}>
                          {/* contacts */}
                          <div style={{ flex: 1, minWidth: 240 }}>
                            <strong style={{ fontSize: 13, color: "var(--heading)" }}>Contacts</strong>
                            {crm.contacts.length === 0 && <p className="muted" style={{ margin: "4px 0" }}>No contacts yet.</p>}
                            {crm.contacts.map((c) => (
                              <div key={c.id} style={{ fontSize: 13, margin: "3px 0" }}>
                                {c.name}
                                {c.role && <span className="muted"> · {c.role}</span>}
                                {c.email && <span className="muted"> · {c.email}</span>}
                              </div>
                            ))}
                            <div className="row" style={{ marginTop: 6 }}>
                              <input placeholder="Name" value={cName} onChange={(e) => setCName(e.target.value)} />
                              <input placeholder="Role" value={cRole} onChange={(e) => setCRole(e.target.value)} />
                              <button
                                style={{ flex: "0 0 auto" }}
                                disabled={!cName}
                                onClick={guard(async () => {
                                  const r = await api.addDealContact(d.id, { name: cName, role: cRole || null });
                                  setCrm(r); setCName(""); setCRole("");
                                }, "Contact added")}
                              >
                                Add
                              </button>
                            </div>
                          </div>
                          {/* activity timeline */}
                          <div style={{ flex: 1.4, minWidth: 280 }}>
                            <strong style={{ fontSize: 13, color: "var(--heading)" }}>Activity</strong>
                            {crm.activities.length === 0 && <p className="muted" style={{ margin: "4px 0" }}>No activity logged.</p>}
                            {crm.activities.map((a) => (
                              <div key={a.id} style={{ fontSize: 13, margin: "4px 0", borderLeft: "2px solid var(--border)", paddingLeft: 8 }}>
                                <span className="badge">{a.kind}</span> <span className="muted">{a.occurred_on}</span>
                                <div>{a.body}</div>
                              </div>
                            ))}
                            <div className="row" style={{ marginTop: 6, alignItems: "flex-end" }}>
                              <select value={actKind} onChange={(e) => setActKind(e.target.value)} style={{ flex: "0 0 auto", width: "auto" }}>
                                {ACT_KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
                              </select>
                              <input type="date" value={actDate} onChange={(e) => setActDate(e.target.value)} style={{ flex: "0 0 auto", width: "auto" }} />
                              <input placeholder="What happened?" value={actBody} onChange={(e) => setActBody(e.target.value)} />
                              <button
                                style={{ flex: "0 0 auto" }}
                                disabled={!actBody}
                                onClick={guard(async () => {
                                  const r = await api.addDealActivity(d.id, { kind: actKind, body: actBody, occurred_on: actDate });
                                  setCrm(r); setActBody("");
                                }, "Activity logged")}
                              >
                                Log
                              </button>
                            </div>
                          </div>
                        </div>
                      )}
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

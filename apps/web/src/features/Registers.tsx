import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import { api, type Charge, type Registration, type SBO } from "../api";

const REG_KINDS = ["gst", "professional_tax", "shops_establishment", "pf", "esic"];

export default function Registers({ entityId }: { entityId: string }) {
  const [sbos, setSbos] = useState<SBO[]>([]);
  const [charges, setCharges] = useState<Charge[]>([]);
  const [regs, setRegs] = useState<Registration[]>([]);
  const { error, setError, guard } = useGuard(() => load());

  const [sName, setSName] = useState("");
  const [sPct, setSPct] = useState("");
  const [cHolder, setCHolder] = useState("");
  const [cAmt, setCAmt] = useState("");
  const [rKind, setRKind] = useState("gst");
  const [rState, setRState] = useState("");
  const [rNum, setRNum] = useState("");

  async function load() {
    try {
      const [s, c, r] = await Promise.all([
        api.listSBO(entityId),
        api.listCharges(entityId),
        api.listRegistrations(entityId),
      ]);
      setSbos(s);
      setCharges(c);
      setRegs(r);
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

      <div className="card">
        <h3>Register of Significant Beneficial Owners (SBO)</h3>
        <div className="row">
          <input placeholder="Name" value={sName} onChange={(e) => setSName(e.target.value)} />
          <input placeholder="% beneficial interest" value={sPct} onChange={(e) => setSPct(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!sName}
            onClick={guard(async () => {
              await api.addSBO(entityId, { name: sName, percentage: sPct || "0" });
              setSName(""); setSPct("");
            })}
          >
            Add SBO
          </button>
        </div>
        {sbos.length > 0 && (
          <ul className="muted">
            {sbos.map((s) => <li key={s.id}>{s.name} — {s.percentage}%</li>)}
          </ul>
        )}
      </div>

      <div className="card">
        <h3>Register of Charges</h3>
        <div className="row">
          <input placeholder="Charge holder / lender" value={cHolder} onChange={(e) => setCHolder(e.target.value)} />
          <input placeholder="Amount ₹" value={cAmt} onChange={(e) => setCAmt(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!cHolder}
            onClick={guard(async () => {
              await api.addCharge(entityId, {
                holder: cHolder, amount: cAmt || "0", charge_type: "hypothecation",
                created_on: new Date().toISOString().slice(0, 10),
              });
              setCHolder(""); setCAmt("");
            })}
          >
            Add charge
          </button>
        </div>
        {charges.length > 0 && (
          <table style={{ marginTop: 8 }}>
            <thead><tr><th>Holder</th><th>Amount</th><th>Status</th><th></th></tr></thead>
            <tbody>
              {charges.map((c) => (
                <tr key={c.id}>
                  <td>{c.holder}</td>
                  <td>₹{c.amount}</td>
                  <td><span className={`badge ${c.satisfied ? "complete" : "active"}`}>{c.satisfied ? "satisfied" : "open"}</span></td>
                  <td>{!c.satisfied && <button className="secondary" onClick={guard(() => api.satisfyCharge(c.id))}>Mark satisfied</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Multi-state registrations</h3>
        <div className="row">
          <select value={rKind} onChange={(e) => setRKind(e.target.value)}>
            {REG_KINDS.map((k) => <option key={k} value={k}>{k.replace(/_/g, " ")}</option>)}
          </select>
          <input placeholder="State" value={rState} onChange={(e) => setRState(e.target.value)} />
          <input placeholder="Number" value={rNum} onChange={(e) => setRNum(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!rState}
            onClick={guard(async () => {
              await api.addRegistration(entityId, { kind: rKind, state: rState, number: rNum || null });
              setRState(""); setRNum("");
            })}
          >
            Add registration
          </button>
        </div>
        {regs.length > 0 && (
          <table style={{ marginTop: 8 }}>
            <thead><tr><th>Type</th><th>State</th><th>Number</th></tr></thead>
            <tbody>
              {regs.map((r) => (
                <tr key={r.id}><td>{r.kind.replace(/_/g, " ")}</td><td>{r.state}</td><td>{r.number || "—"}</td></tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

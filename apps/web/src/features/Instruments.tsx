import { useEffect, useState } from "react";
import { fmtMoney } from "../lib/format";
import KindBadge from "../components/KindBadge";
import Stepper, { type StepState } from "../components/Stepper";
import { useGuard } from "../hooks";
import { api, type Instrument, type InstrumentExecution, type SecurityClass } from "../api";

function execSteps(ex: InstrumentExecution): { label: string; state: StepState }[] {
  const state = (value: string | null, doneValues: string[]): StepState =>
    value === null ? "todo" : doneValues.includes(value) ? "done" : "active";
  return [
    { label: "board", state: state(ex.board, ["passed"]) },
    { label: "agreement", state: state(ex.agreement, ["signed"]) },
    { label: "e-sign", state: state(ex.signature, ["completed"]) },
  ];
}

export default function Instruments({
  entityId,
  onChanged,
}: {
  entityId: string;
  onChanged?: () => void;
}) {
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [execution, setExecution] = useState<Record<string, InstrumentExecution>>({});
  const [classes, setClasses] = useState<SecurityClass[]>([]);
  const { error, setError, guard } = useGuard(() => load());
  const [note, setNote] = useState("");

  // create form
  const [name, setName] = useState("");
  const [kind, setKind] = useState("angel");
  const [email, setEmail] = useState("");
  const [type, setType] = useState("safe");
  const [principal, setPrincipal] = useState("");
  const [cap, setCap] = useState("");
  const [discount, setDiscount] = useState("");
  // convert controls
  const [roundPrice, setRoundPrice] = useState("100");
  const [convClass, setConvClass] = useState("");

  async function load() {
    try {
      const [i, c, ex] = await Promise.all([
        api.listInstruments(entityId),
        api.listSecurityClasses(entityId),
        api.instrumentsExecution(entityId),
      ]);
      setInstruments(i);
      setClasses(c);
      setExecution(ex);
      if (!convClass && c.length) setConvClass(c[0].id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  return (
    <div className="card">
      <h3>SAFEs &amp; convertible notes</h3>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      <p className="muted">
        Family, friends and angels can invest here — tag each cheque; the private-placement
        limit (200 offerees per FY, Sec 42) is enforced automatically.
      </p>
      <div className="row">
        <input placeholder="Investor" value={name} onChange={(e) => setName(e.target.value)} />
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="friend_family">Friends &amp; family</option>
          <option value="angel">Angel</option>
          <option value="institutional">Institutional</option>
        </select>
        <input placeholder="Email (for their portal)" value={email} onChange={(e) => setEmail(e.target.value)} />
        <select value={type} onChange={(e) => setType(e.target.value)}>
          <option value="safe">SAFE</option>
          <option value="convertible_note">Convertible note</option>
        </select>
        <input placeholder="Principal ₹" value={principal} onChange={(e) => setPrincipal(e.target.value)} />
        <input placeholder="Val cap ₹ (opt)" value={cap} onChange={(e) => setCap(e.target.value)} />
        <input placeholder="Discount e.g. 0.2" value={discount} onChange={(e) => setDiscount(e.target.value)} />
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!name || !principal}
          onClick={guard(async () => {
            await api.createInstrument(entityId, {
              investor_name: name,
              investor_email: email || null,
              investor_kind: kind,
              instrument_type: type,
              principal,
              valuation_cap: cap || null,
              discount_pct: discount || "0",
              issue_date: new Date().toISOString().slice(0, 10),
            });
            setName(""); setEmail(""); setPrincipal(""); setCap(""); setDiscount("");
          })}
        >
          Add
        </button>
      </div>

      <div className="row" style={{ marginTop: 8 }}>
        <span className="muted" style={{ alignSelf: "center" }}>Convert at round price ₹</span>
        <input style={{ maxWidth: 120 }} value={roundPrice} onChange={(e) => setRoundPrice(e.target.value)} />
        <select value={convClass} onChange={(e) => setConvClass(e.target.value)} style={{ maxWidth: 200 }}>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
      </div>

      {instruments.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Investor</th><th>Kind</th><th>Type</th><th>Principal</th><th>Cap</th><th>Disc</th><th>Status</th><th>Execution</th><th></th></tr>
          </thead>
          <tbody>
            {instruments.map((x) => {
              const ex = execution[x.id];
              return (
              <tr key={x.id}>
                <td>{x.investor_name}</td>
                <td><KindBadge kind={x.investor_kind} /></td>
                <td>{x.instrument_type === "safe" ? "SAFE" : "Note"}</td>
                <td>{fmtMoney(x.principal)}</td>
                <td>{x.valuation_cap ? `₹${x.valuation_cap}` : "—"}</td>
                <td>{Number(x.discount_pct) > 0 ? `${(Number(x.discount_pct) * 100).toFixed(0)}%` : "—"}</td>
                <td>
                  <span className={`badge ${x.status === "converted" ? "complete" : ""}`}>
                    {x.status}{x.converted_shares ? ` (${x.converted_shares.toLocaleString()})` : ""}
                  </span>
                </td>
                <td>
                  {ex && <Stepper steps={execSteps(ex)} />}
                  <br />
                  {ex && !ex.board && (
                    <button
                      className="secondary"
                      title="Draft the circular board resolution approving this issuance"
                      onClick={guard(async () => {
                        await api.requestInstrumentBoardApproval(x.id);
                        setNote(`Board approval drafted for ${x.investor_name} — pass it in Board & Resolutions.`);
                      })}
                    >
                      Board approval
                    </button>
                  )}{" "}
                  {ex && !ex.agreement && (
                    <button
                      className="secondary"
                      onClick={guard(async () => {
                        await api.generateInstrumentAgreement(x.id);
                        setNote(`Agreement generated for ${x.investor_name} (see Documents).`);
                      })}
                    >
                      Agreement
                    </button>
                  )}
                </td>
                <td>
                  {x.status === "outstanding" && convClass && (
                    <button
                      className="secondary"
                      onClick={guard(async () => {
                        const r = await api.convertInstrument(x.id, {
                          round_price_per_share: roundPrice,
                          security_class_id: convClass,
                        });
                        setNote(`${x.investor_name}: converted to ${r.converted_shares.toLocaleString()} shares @ ₹${r.conversion_price}.`);
                        onChanged?.();
                      })}
                    >
                      Convert
                    </button>
                  )}
                </td>
              </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}

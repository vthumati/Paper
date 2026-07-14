import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import { api, type Deal } from "../api";

const STAGES = ["sourced", "screening", "diligence", "ic", "term_sheet", "invested", "passed"];

/** GP-side deal flow: sourced → screening → diligence → IC → term sheet → invested. */
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
            <tr><th>Company</th><th>Sector</th><th>Cheque</th><th>Stage</th><th></th></tr>
          </thead>
          <tbody>
            {deals.map((d) => (
              <tr key={d.id}>
                <td>{d.company_name}</td>
                <td>{d.sector ?? "—"}</td>
                <td>₹{d.amount}</td>
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
                  {d.stage !== "invested" && d.stage !== "passed" && (
                    <button
                      className="secondary"
                      onClick={guard(async () => {
                        const pct = window.prompt(`Ownership % acquired in ${d.company_name}:`, "10");
                        await api.investDeal(d.id, { ownership_pct: pct || "0" });
                        onInvested?.();
                      })}
                    >
                      Invest
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

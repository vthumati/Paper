import { useEffect, useState } from "react";
import {
  api,
  type DematRec,
  type FounderVesting,
  type SecurityClass,
  type Stakeholder,
  type WaterfallRange,
  type WaterfallResult,
} from "../api";
import BarChart from "../components/BarChart";

export default function CapTableAdvanced({
  entityId,
  onChanged,
  features,
}: {
  entityId: string;
  onChanged?: () => void;
  features?: Record<string, boolean>;
}) {
  const feat = (k: string) => !features || features[k] !== false;
  const [classes, setClasses] = useState<SecurityClass[]>([]);
  const [holders, setHolders] = useState<Stakeholder[]>([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  // transfer
  const [tSc, setTSc] = useState("");
  const [tFrom, setTFrom] = useState("");
  const [tTo, setTTo] = useState("");
  const [tQty, setTQty] = useState("");
  const [tPrice, setTPrice] = useState("");
  // conversion
  const [cFrom, setCFrom] = useState("");
  const [cTo, setCTo] = useState("");
  const [cSh, setCSh] = useState("");
  const [cQty, setCQty] = useState("");
  const [cRatio, setCRatio] = useState("1");
  // corporate action
  const [caType, setCaType] = useState("split");
  const [caSc, setCaSc] = useState("");
  const [caNum, setCaNum] = useState("");
  const [caDen, setCaDen] = useState("1");
  // waterfall
  const [exit, setExit] = useState("");
  const [wf, setWf] = useState<WaterfallResult | null>(null);
  const [rangeIn, setRangeIn] = useState("");
  const [range, setRange] = useState<WaterfallRange | null>(null);
  // demat
  const [demat, setDemat] = useState<DematRec[]>([]);
  const [dSc, setDSc] = useState("");
  const [dIsin, setDIsin] = useState("");
  // founder vesting
  const [fv, setFv] = useState<FounderVesting[]>([]);
  const [fvSh, setFvSh] = useState("");
  const [fvSc, setFvSc] = useState("");
  const [fvQty, setFvQty] = useState("");
  const [fvStart, setFvStart] = useState("2025-01-01");

  async function load() {
    try {
      const [c, h, d, f] = await Promise.all([
        api.listSecurityClasses(entityId),
        api.listStakeholders(entityId),
        api.listDemat(entityId),
        api.listFounderVesting(entityId),
      ]);
      setClasses(c);
      setHolders(h);
      setDemat(d);
      setFv(f);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  const act = (fn: () => Promise<unknown>, msg: string) => async () => {
    setError("");
    setNote("");
    try {
      await fn();
      setNote(msg);
      await load();
      onChanged?.();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const clsName = (id: string) => classes.find((c) => c.id === id)?.name ?? "—";

  return (
    <div>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      <div className="row">
        {feat("transfers") && (
        <div className="card" style={{ flex: 1 }}>
          <h3>Transfer (SH-4)</h3>
          <select value={tSc} onChange={(e) => setTSc(e.target.value)}>
            <option value="">security class…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select value={tFrom} onChange={(e) => setTFrom(e.target.value)}>
            <option value="">from…</option>
            {holders.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
          <select value={tTo} onChange={(e) => setTTo(e.target.value)}>
            <option value="">to…</option>
            {holders.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
          <div className="row">
            <input placeholder="Qty" value={tQty} onChange={(e) => setTQty(e.target.value)} />
            <input placeholder="Price/share" value={tPrice} onChange={(e) => setTPrice(e.target.value)} />
          </div>
          <div style={{ marginTop: 8 }}>
            <button
              disabled={!tSc || !tFrom || !tTo || !tQty}
              onClick={act(
                () => api.createTransfer(entityId, { security_class_id: tSc, from_stakeholder_id: tFrom, to_stakeholder_id: tTo, quantity: Number(tQty), price_per_unit: tPrice || "0" }),
                "Transfer recorded (stamp duty computed)."
              )}
            >
              Transfer
            </button>
          </div>
        </div>
        )}

        {feat("conversions") && (
        <div className="card" style={{ flex: 1 }}>
          <h3>Convert</h3>
          <select value={cSh} onChange={(e) => setCSh(e.target.value)}>
            <option value="">holder…</option>
            {holders.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
          <select value={cFrom} onChange={(e) => setCFrom(e.target.value)}>
            <option value="">from class…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <select value={cTo} onChange={(e) => setCTo(e.target.value)}>
            <option value="">to class…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <div className="row">
            <input placeholder="Qty" value={cQty} onChange={(e) => setCQty(e.target.value)} />
            <input placeholder="Ratio" value={cRatio} onChange={(e) => setCRatio(e.target.value)} />
          </div>
          <div style={{ marginTop: 8 }}>
            <button
              disabled={!cSh || !cFrom || !cTo || !cQty}
              onClick={act(
                () => api.createConversion(entityId, { stakeholder_id: cSh, from_class_id: cFrom, to_class_id: cTo, from_quantity: Number(cQty), ratio: cRatio || "1" }),
                `Converted ${cQty} ${clsName(cFrom)} → ${clsName(cTo)}.`
              )}
            >
              Convert
            </button>
          </div>
        </div>
        )}
      </div>

      {feat("corporate_actions") && (
      <div className="card">
        <h3>Corporate action (split / bonus)</h3>
        <div className="row">
          <select value={caType} onChange={(e) => setCaType(e.target.value)}>
            <option value="split">Split</option>
            <option value="bonus">Bonus</option>
          </select>
          <select value={caSc} onChange={(e) => setCaSc(e.target.value)}>
            <option value="">security class…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input placeholder="numerator" value={caNum} onChange={(e) => setCaNum(e.target.value)} />
          <input placeholder="denominator" value={caDen} onChange={(e) => setCaDen(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!caSc || !caNum}
            onClick={act(
              () => api.createCorporateAction(entityId, { security_class_id: caSc, type: caType, numerator: Number(caNum), denominator: Number(caDen) || 1 }),
              caType === "split" ? `Split ${caNum}:${caDen} applied.` : `Bonus ${caNum}:${caDen} applied.`
            )}
          >
            Apply
          </button>
        </div>
        <p className="muted">Split 1:10 → numerator 10, denominator 1. Bonus 1:1 → numerator 1, denominator 1.</p>
      </div>
      )}

      {feat("founder_vesting") && (
      <div className="card">
        <h3>Founder reverse-vesting</h3>
        <div className="row">
          <select value={fvSh} onChange={(e) => setFvSh(e.target.value)}>
            <option value="">founder…</option>
            {holders.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
          <select value={fvSc} onChange={(e) => setFvSc(e.target.value)}>
            <option value="">class…</option>
            {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <input placeholder="Total shares" value={fvQty} onChange={(e) => setFvQty(e.target.value)} />
          <input type="date" value={fvStart} onChange={(e) => setFvStart(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!fvSh || !fvSc || !fvQty}
            onClick={act(
              () => api.createFounderVesting(entityId, { stakeholder_id: fvSh, security_class_id: fvSc, total_shares: Number(fvQty), start_date: fvStart }),
              "Founder vesting schedule created."
            )}
          >
            Add vesting
          </button>
        </div>
        {fv.length > 0 && (
          <table style={{ marginTop: 8 }}>
            <thead><tr><th>Founder</th><th>Total</th><th>Vested</th><th>Unvested</th><th></th></tr></thead>
            <tbody>
              {fv.map((v) => (
                <tr key={v.id}>
                  <td>{holders.find((h) => h.id === v.stakeholder_id)?.name ?? v.stakeholder_id}</td>
                  <td>{v.total_shares.toLocaleString()}</td>
                  <td>{v.vested.toLocaleString()}</td>
                  <td>{v.unvested.toLocaleString()}</td>
                  <td>
                    {!v.repurchased ? (
                      <button className="secondary" onClick={act(() => api.repurchaseUnvested(v.id), "Unvested shares repurchased.")}>
                        Repurchase unvested
                      </button>
                    ) : <span className="badge">repurchased</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      )}

      <div className="card">
        <h3>{feat("demat") ? "Demat / ISIN" : "Exports"}</h3>
        <div className="row">
          {feat("demat") && (
            <>
              <select value={dSc} onChange={(e) => setDSc(e.target.value)}>
                <option value="">security class…</option>
                {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
              <input placeholder="ISIN" value={dIsin} onChange={(e) => setDIsin(e.target.value)} />
              <button
                style={{ flex: "0 0 auto" }}
                disabled={!dSc}
                onClick={act(
                  () => api.addDemat(entityId, { security_class_id: dSc, isin: dIsin || null, status: "dematerialised" }),
                  "Demat / ISIN recorded."
                )}
              >
                Record demat
              </button>
            </>
          )}
          <button
            className="secondary"
            style={{ flex: "0 0 auto" }}
            onClick={() => api.downloadCapTableCsv(entityId)}
          >
            Export cap table (CSV)
          </button>
        </div>
        {feat("demat") && demat.length > 0 && (
          <ul className="muted">
            {demat.map((d) => (
              <li key={d.id}>
                {classes.find((c) => c.id === d.security_class_id)?.name ?? d.security_class_id}:{" "}
                {d.isin || "—"} ({d.depository}, {d.status})
              </li>
            ))}
          </ul>
        )}
      </div>

      {feat("waterfall") && (
      <div className="card">
        <h3>Liquidation waterfall</h3>
        <p className="muted">Model an exit: preferences (by seniority) first, then the remainder pro-rata.</p>
        <div className="row">
          <input placeholder="Exit amount ₹" value={exit} onChange={(e) => setExit(e.target.value)} />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!exit}
            onClick={async () => {
              setError("");
              try {
                setWf(await api.waterfall(entityId, exit));
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Compute
          </button>
        </div>
        {wf && (
          <>
            <p className="muted">Distributed ₹{wf.distributed} of ₹{wf.exit_amount}</p>
            <BarChart
              bars={wf.payouts.map((p) => ({
                label: p.stakeholder_name ?? "—",
                value: Number(p.payout),
                display: `₹${Number(p.payout).toLocaleString("en-IN")}`,
              }))}
            />
          </>
        )}

        <div className="row" style={{ marginTop: 12 }}>
          <input
            placeholder="Compare exits, e.g. 100000000, 500000000"
            value={rangeIn}
            onChange={(e) => setRangeIn(e.target.value)}
          />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!rangeIn}
            onClick={async () => {
              setError("");
              try {
                setRange(await api.waterfallRange(entityId, rangeIn));
              } catch (e) {
                setError((e as Error).message);
              }
            }}
          >
            Compare
          </button>
        </div>
        {range && (
          <table style={{ marginTop: 8 }}>
            <thead>
              <tr>
                <th>Stakeholder</th>
                {range.exit_amounts.map((a, i) => <th key={i}>Exit ₹{Number(a).toLocaleString()}</th>)}
              </tr>
            </thead>
            <tbody>
              {range.rows.map((r) => (
                <tr key={r.stakeholder_id}>
                  <td>{r.stakeholder_name}</td>
                  {r.payouts.map((p, i) => <td key={i}>₹{p}</td>)}
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

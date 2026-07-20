import { useEffect, useState } from "react";
import { fmtMoney } from "../lib/format";
import { api, type LiquidityEvent } from "../api";

/** Company liquidity windows (buyback/tender): open a window, holders tender
 * via their portal, then settle to buy the tendered shares back. */
export default function Liquidity({ entityId, onChanged }: { entityId: string; onChanged?: () => void }) {
  const [events, setEvents] = useState<LiquidityEvent[]>([]);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");
  const [name, setName] = useState("");
  const [price, setPrice] = useState("");
  const [opens, setOpens] = useState("");
  const [closes, setCloses] = useState("");

  function load() {
    api.listLiquidityEvents(entityId).then(setEvents).catch((e) => setError(e.message));
  }
  useEffect(load, [entityId]);

  const act = (fn: () => Promise<unknown>) => async () => {
    setError(""); setNote("");
    try {
      await fn();
      load();
      onChanged?.();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="card">
      <h2>Liquidity events</h2>
      <p className="muted">
        Open a buyback window at a fixed price. Shareholders tender from their portal; settling
        buys the tendered shares back into the cap table.
      </p>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}
      <div className="row">
        <input placeholder="Name (e.g. 2026 Buyback)" value={name} onChange={(e) => setName(e.target.value)} />
        <input placeholder="Price/share ₹" value={price} onChange={(e) => setPrice(e.target.value)} />
        <div>
          <label>Opens</label>
          <input type="date" value={opens} onChange={(e) => setOpens(e.target.value)} />
        </div>
        <div>
          <label>Closes</label>
          <input type="date" value={closes} onChange={(e) => setCloses(e.target.value)} />
        </div>
        <button
          style={{ flex: "0 0 auto", alignSelf: "flex-end" }}
          disabled={!name || !price || !opens || !closes}
          onClick={act(async () => {
            await api.createLiquidityEvent(entityId, {
              name, price_per_share: price, opens_on: opens, closes_on: closes,
            });
            setName(""); setPrice(""); setOpens(""); setCloses("");
          })}
        >
          Open window
        </button>
      </div>
      {events.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th>Name</th><th>Price</th><th>Window</th><th>Tenders</th>
              <th>Shares</th><th>Indicative payout</th><th>Status</th><th></th>
            </tr>
          </thead>
          <tbody>
            {events.map((ev) => (
              <tr key={ev.id}>
                <td>{ev.name}</td>
                <td>{fmtMoney(ev.price_per_share)}</td>
                <td className="muted">{ev.opens_on} → {ev.closes_on}</td>
                <td>{ev.tenders}</td>
                <td>{ev.shares_tendered.toLocaleString()}</td>
                <td>{fmtMoney(ev.indicative_payout)}</td>
                <td>
                  <span className={`badge ${ev.status === "settled" ? "complete" : ev.status === "open" ? "active" : ""}`}>
                    {ev.status}
                  </span>
                </td>
                <td>
                  {ev.status === "open" && (
                    <button
                      className="secondary"
                      onClick={act(async () => {
                        const r = await api.settleLiquidityEvent(entityId, ev.id);
                        setNote(`Settled: bought back ${r.shares_bought_back.toLocaleString()} shares for ₹${r.total_paid}.`);
                      })}
                    >
                      Settle
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

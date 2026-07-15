import { useState } from "react";
import { api, type Scenario } from "../api";

/** Pro-forma round modeling: what the cap table looks like AFTER a
 *  hypothetical round — nothing is written to the ledger. */
export default function ScenarioModeling({ entityId }: { entityId: string }) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [newMoney, setNewMoney] = useState("");
  const [preMoney, setPreMoney] = useState("");
  const [price, setPrice] = useState("");
  const [topUp, setTopUp] = useState("");
  const [error, setError] = useState("");

  const holders = [...new Set(scenarios.flatMap((s) => s.rows.map((r) => r.name ?? "—")))];

  return (
    <div className="card">
      <h3>Scenario modeling (pro-forma)</h3>
      <p className="muted">
        Model a hypothetical round — new money, pre-money or price, optional ESOP pool top-up
        (created pre-money). SAFEs convert at the scenario price. Nothing touches the ledger.
      </p>
      {error && <p className="error">{error}</p>}
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div><label>New money (₹)</label><input value={newMoney} onChange={(e) => setNewMoney(e.target.value)} /></div>
        <div><label>Pre-money (₹)</label><input value={preMoney} onChange={(e) => setPreMoney(e.target.value)} placeholder="or set price →" /></div>
        <div><label>Price/share (₹)</label><input value={price} onChange={(e) => setPrice(e.target.value)} /></div>
        <div><label>Pool top-up (shares)</label><input value={topUp} onChange={(e) => setTopUp(e.target.value)} /></div>
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!newMoney || (!preMoney && !price)}
          onClick={async () => {
            setError("");
            try {
              const s = await api.modelScenario(entityId, {
                new_money: newMoney,
                pre_money: preMoney || null,
                price_per_share: price || null,
                pool_top_up: Number(topUp) || 0,
              });
              setScenarios([...scenarios, s]);
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Add scenario
        </button>
        {scenarios.length > 0 && (
          <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => setScenarios([])}>
            Clear
          </button>
        )}
      </div>

      {scenarios.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th></th>
              {scenarios.map((s, i) => (
                <th key={i}>₹{Number(s.new_money).toLocaleString()} @ pre ₹{Number(s.pre_money).toLocaleString()}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr><td>Price / share</td>{scenarios.map((s, i) => <td key={i}>₹{s.price_per_share}</td>)}</tr>
            <tr><td>Post-money</td>{scenarios.map((s, i) => <td key={i}>₹{Number(s.post_money).toLocaleString()}</td>)}</tr>
            <tr><td>New shares</td>{scenarios.map((s, i) => <td key={i}>{s.new_shares.toLocaleString()}</td>)}</tr>
            <tr><td>SAFEs convert to</td>{scenarios.map((s, i) => <td key={i}>{s.safe_shares_converted.toLocaleString()}</td>)}</tr>
            <tr><td>FD after</td>{scenarios.map((s, i) => <td key={i}>{s.fd_post.toLocaleString()}</td>)}</tr>
            {holders.map((name) => (
              <tr key={name}>
                <td>{name} %</td>
                {scenarios.map((s, i) => {
                  const r = s.rows.find((x) => (x.name ?? "—") === name);
                  return (
                    <td key={i}>
                      {r ? (
                        <>
                          {r.after_pct}%{" "}
                          {r.dilution_pct !== 0 && (
                            <span className="muted">({r.dilution_pct > 0 ? "+" : ""}{r.dilution_pct})</span>
                          )}
                        </>
                      ) : "—"}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

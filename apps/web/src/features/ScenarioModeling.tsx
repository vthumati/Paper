import { useState } from "react";
import { fmtMoney } from "../lib/format";
import { api, type Scenario } from "../api";
import PageHeader from "../components/PageHeader";

/** Pro-forma round modeling: what the cap table looks like AFTER a
 *  hypothetical round — nothing is written to the ledger. */
export default function ScenarioModeling({ entityId }: { entityId: string }) {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [newMoney, setNewMoney] = useState("");
  const [preMoney, setPreMoney] = useState("");
  const [price, setPrice] = useState("");
  const [topUp, setTopUp] = useState("");
  const [poolTiming, setPoolTiming] = useState<"pre" | "post">("pre");
  const [error, setError] = useState("");

  const holders = [...new Set(scenarios.flatMap((s) => s.rows.map((r) => r.name ?? "—")))];

  return (
    <div className="card">
      <PageHeader icon="📊" title="Scenario modeling" subtitle="Pro-forma cap table after a hypothetical round" />
      <p className="muted">
        Model a hypothetical round — new money, pre-money or price, optional ESOP pool top-up.
        Choose whether the pool is created <strong>pre-money</strong> (comes out of existing
        holders) or <strong>post-money</strong> (dilutes everyone, new investors included). SAFEs
        convert at the scenario price. Nothing touches the ledger.
      </p>
      {error && <p className="error">{error}</p>}
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div><label>New money (₹)</label><input value={newMoney} onChange={(e) => setNewMoney(e.target.value)} /></div>
        <div><label>Pre-money (₹)</label><input value={preMoney} onChange={(e) => setPreMoney(e.target.value)} placeholder="or set price →" /></div>
        <div><label>Price/share (₹)</label><input value={price} onChange={(e) => setPrice(e.target.value)} /></div>
        <div><label>Pool top-up (shares)</label><input value={topUp} onChange={(e) => setTopUp(e.target.value)} /></div>
        <div>
          <label>Pool timing</label>
          <select
            value={poolTiming}
            onChange={(e) => setPoolTiming(e.target.value as "pre" | "post")}
            disabled={!Number(topUp)}
            title="Pre-money dilutes existing holders; post-money dilutes everyone incl. new investors"
          >
            <option value="pre">Pre-money</option>
            <option value="post">Post-money</option>
          </select>
        </div>
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
                pool_timing: poolTiming,
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

      {scenarios.length > 0 && (() => {
        const latest = scenarios[scenarios.length - 1];
        const hasSafes = latest.safe_shares_converted > 0;
        const delta = (curr: number, prev: number) => {
          const d = Math.round((curr - prev) * 10000) / 10000;
          if (d < 0) return <span className="delta-down"> ▼ {Math.abs(d)}%</span>;
          if (d > 0) return <span className="delta-up"> ▲ {d}%</span>;
          return null;
        };
        return (
          <div style={{ marginTop: 12 }}>
            <h4 style={{ margin: "4px 0" }}>
              Stage breakdown — latest scenario ({fmtMoney(Number(latest.new_money))} @ pre{" "}
              {fmtMoney(Number(latest.pre_money))})
              {latest.pool_top_up > 0 && (
                <span className="muted" style={{ fontWeight: 400 }}>
                  {" "}· {latest.pool_top_up.toLocaleString()}-share pool created{" "}
                  {latest.pool_timing === "post" ? "post-money" : "pre-money"}
                </span>
              )}
            </h4>
            <table>
              <thead>
                <tr>
                  <th>Holder</th>
                  <th>Today</th>
                  {hasSafes && <th>After SAFEs convert</th>}
                  <th>After the round</th>
                </tr>
              </thead>
              <tbody>
                {latest.rows.map((r) => (
                  <tr key={r.name ?? "—"}>
                    <td>{r.name ?? "—"}</td>
                    <td>
                      {r.before_pct}%
                      <div className="muted">{r.before.toLocaleString()} shares</div>
                    </td>
                    {hasSafes && (
                      <td>
                        {r.after_safes_pct}%{delta(r.after_safes_pct, r.before_pct)}
                      </td>
                    )}
                    <td>
                      {r.after_pct}%{delta(r.after_pct, hasSafes ? r.after_safes_pct : r.before_pct)}
                      <div className="muted">{r.after.toLocaleString()} shares</div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })()}

      {scenarios.length > 1 && <h4 style={{ margin: "14px 0 4px" }}>Scenario comparison</h4>}
      {scenarios.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr>
              <th></th>
              {scenarios.map((s, i) => (
                <th key={i}>{fmtMoney(Number(s.new_money))} @ pre {fmtMoney(Number(s.pre_money))}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            <tr><td>Price / share</td>{scenarios.map((s, i) => <td key={i}>{fmtMoney(s.price_per_share)}</td>)}</tr>
            <tr><td>Post-money</td>{scenarios.map((s, i) => <td key={i}>{fmtMoney(Number(s.post_money))}</td>)}</tr>
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
                          {r.dilution_pct < 0 && (
                            <span className="delta-down">▼ {Math.abs(r.dilution_pct)}%</span>
                          )}
                          {r.dilution_pct > 0 && (
                            <span className="delta-up">▲ {r.dilution_pct}%</span>
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

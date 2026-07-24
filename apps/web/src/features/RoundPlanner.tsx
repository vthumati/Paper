import { useEffect, useRef, useState } from "react";
import { api, type RoundPlan } from "../api";
import { fmtMoney } from "../lib/format";
import StackedBar from "../components/StackedBar";
import PageHeader from "../components/PageHeader";

let _uid = 0;
const uid = () => `t${++_uid}`;

interface CoInv {
  id: string;
  name: string;
  amount: string;
}
interface Tier {
  id: string;
  name: string;
  amount: string;
  coInvestors: CoInv[];
}

/** Interactive round planner: build a priced round from multiple investor
 *  tiers (each optionally split among co-investors), toggle down-round
 *  anti-dilution, and watch the pro-forma cap table recompute live. */
export default function RoundPlanner({ entityId }: { entityId: string }) {
  const [preMoney, setPreMoney] = useState("40000000");
  const [price, setPrice] = useState("");
  const [topUp, setTopUp] = useState("");
  const [poolTiming, setPoolTiming] = useState<"pre" | "post">("pre");
  const [applyAd, setApplyAd] = useState(true);
  const [tiers, setTiers] = useState<Tier[]>([
    { id: uid(), name: "Lead", amount: "10000000", coInvestors: [] },
  ]);
  const [plan, setPlan] = useState<RoundPlan | null>(null);
  const [error, setError] = useState("");
  const dragId = useRef<string | null>(null);

  // live recompute (debounced) whenever any input changes
  useEffect(() => {
    if (!preMoney && !price) {
      setPlan(null);
      return;
    }
    const body = {
      pre_money: price ? null : preMoney || null,
      price_per_share: price || null,
      pool_top_up: Number(topUp) || 0,
      pool_timing: poolTiming,
      apply_anti_dilution: applyAd,
      tiers: tiers.map((t) => ({
        name: t.name || "Tier",
        amount: t.coInvestors.length ? 0 : Number(t.amount) || 0,
        co_investors: t.coInvestors.map((c) => ({
          name: c.name || "Co-investor",
          amount: Number(c.amount) || 0,
        })),
      })),
    };
    const handle = setTimeout(async () => {
      try {
        setError("");
        setPlan(await api.planRound(entityId, body));
      } catch (e) {
        setError((e as Error).message);
      }
    }, 350);
    return () => clearTimeout(handle);
  }, [entityId, preMoney, price, topUp, poolTiming, applyAd, tiers]);

  const patchTier = (id: string, patch: Partial<Tier>) =>
    setTiers((ts) => ts.map((t) => (t.id === id ? { ...t, ...patch } : t)));
  const addTier = () =>
    setTiers((ts) => [...ts, { id: uid(), name: `Tier ${ts.length + 1}`, amount: "", coInvestors: [] }]);
  const removeTier = (id: string) => setTiers((ts) => ts.filter((t) => t.id !== id));
  const addCo = (id: string) =>
    setTiers((ts) =>
      ts.map((t) =>
        t.id === id
          ? { ...t, coInvestors: [...t.coInvestors, { id: uid(), name: "", amount: "" }] }
          : t
      )
    );
  const patchCo = (tid: string, cid: string, patch: Partial<CoInv>) =>
    setTiers((ts) =>
      ts.map((t) =>
        t.id === tid
          ? { ...t, coInvestors: t.coInvestors.map((c) => (c.id === cid ? { ...c, ...patch } : c)) }
          : t
      )
    );
  const removeCo = (tid: string, cid: string) =>
    setTiers((ts) =>
      ts.map((t) =>
        t.id === tid ? { ...t, coInvestors: t.coInvestors.filter((c) => c.id !== cid) } : t
      )
    );

  // drag-to-reorder tiers
  const onDrop = (targetId: string) => {
    const from = dragId.current;
    dragId.current = null;
    if (!from || from === targetId) return;
    setTiers((ts) => {
      const arr = [...ts];
      const fi = arr.findIndex((t) => t.id === from);
      const ti = arr.findIndex((t) => t.id === targetId);
      if (fi < 0 || ti < 0) return ts;
      const [moved] = arr.splice(fi, 1);
      arr.splice(ti, 0, moved);
      return arr;
    });
  };

  const delta = (d: number) => {
    if (d < 0) return <span className="delta-down"> ▼ {Math.abs(d)}%</span>;
    if (d > 0) return <span className="delta-up"> ▲ {d}%</span>;
    return null;
  };

  // post-round ownership bar: top holders + an aggregated "Others"
  const barSegments = (() => {
    if (!plan) return [];
    const held = plan.rows.filter((r) => r.after > 0).sort((a, b) => b.after - a.after);
    const top = held.slice(0, 8).map((r) => ({ label: r.name ?? "—", value: r.after }));
    const rest = held.slice(8).reduce((s, r) => s + r.after, 0);
    if (rest > 0) top.push({ label: "Others", value: rest });
    return top;
  })();

  return (
    <div className="card">
      <PageHeader icon="🧮" title="Round planner" subtitle="Build a priced round from investor tiers — recomputes live" />
      <p className="muted">
        Add investor tiers (drag to reorder) and split any tier among co-investors. The pro-forma
        cap table, dilution and post-money update in real time. Down-round anti-dilution for
        protected preferred classes is folded in automatically. Nothing touches the ledger.
      </p>
      {error && <p className="error">{error}</p>}

      <div className="row" style={{ alignItems: "flex-end", flexWrap: "wrap" }}>
        <div>
          <label>Pre-money (₹)</label>
          <input value={preMoney} onChange={(e) => setPreMoney(e.target.value)} placeholder="or set price →" />
        </div>
        <div>
          <label>Price/share (₹)</label>
          <input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="overrides pre-money" />
        </div>
        <div>
          <label>Pool top-up (shares)</label>
          <input value={topUp} onChange={(e) => setTopUp(e.target.value)} />
        </div>
        <div>
          <label>Pool timing</label>
          <select value={poolTiming} onChange={(e) => setPoolTiming(e.target.value as "pre" | "post")} disabled={!Number(topUp)}>
            <option value="pre">Pre-money</option>
            <option value="post">Post-money</option>
          </select>
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 6, flex: "0 0 auto" }}>
          <input type="checkbox" checked={applyAd} onChange={(e) => setApplyAd(e.target.checked)} />
          Apply anti-dilution
        </label>
      </div>

      <h4 style={{ margin: "14px 0 6px" }}>Investor tiers</h4>
      {tiers.map((t) => (
        <div
          key={t.id}
          className="card"
          onDragOver={(e) => e.preventDefault()}
          onDrop={() => onDrop(t.id)}
          style={{ padding: 12, margin: "0 0 8px", background: "var(--surface-2, #f6f7f5)" }}
        >
          <div className="row" style={{ alignItems: "flex-end" }}>
            <span
              draggable
              onDragStart={() => (dragId.current = t.id)}
              title="Drag to reorder"
              style={{ alignSelf: "center", color: "var(--muted)", cursor: "grab", fontSize: 18 }}
            >
              ⠿
            </span>
            <div style={{ flex: 2 }}>
              <label>Tier name</label>
              <input value={t.name} onChange={(e) => patchTier(t.id, { name: e.target.value })} />
            </div>
            {t.coInvestors.length === 0 && (
              <div style={{ flex: 2 }}>
                <label>Amount (₹)</label>
                <input value={t.amount} onChange={(e) => patchTier(t.id, { amount: e.target.value })} />
              </div>
            )}
            <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => addCo(t.id)}>
              + Co-investor
            </button>
            <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => removeTier(t.id)}>
              Remove
            </button>
          </div>
          {t.coInvestors.length > 0 && (
            <div style={{ marginTop: 8, paddingLeft: 24 }}>
              <div className="muted" style={{ fontSize: 12, marginBottom: 4 }}>
                Co-investors split this tier's allocation:
              </div>
              {t.coInvestors.map((c) => (
                <div className="row" key={c.id} style={{ alignItems: "flex-end", marginBottom: 4 }}>
                  <div style={{ flex: 2 }}>
                    <input placeholder="Co-investor name" value={c.name} onChange={(e) => patchCo(t.id, c.id, { name: e.target.value })} />
                  </div>
                  <div style={{ flex: 2 }}>
                    <input placeholder="Amount (₹)" value={c.amount} onChange={(e) => patchCo(t.id, c.id, { amount: e.target.value })} />
                  </div>
                  <button className="secondary" style={{ flex: "0 0 auto" }} onClick={() => removeCo(t.id, c.id)}>
                    ✕
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
      <button className="secondary" onClick={addTier}>+ Add tier</button>

      {plan && (
        <div style={{ marginTop: 16 }}>
          <div className="row" style={{ gap: 20, flexWrap: "wrap" }}>
            <Metric label="Price / share" value={fmtMoney(plan.price_per_share)} />
            <Metric label="Pre-money" value={fmtMoney(plan.pre_money)} />
            <Metric label="Raising" value={fmtMoney(plan.new_money)} />
            <Metric label="Post-money" value={fmtMoney(plan.post_money)} />
            <Metric label="New shares" value={plan.new_shares.toLocaleString()} />
            {plan.anti_dilution_shares > 0 && (
              <Metric label="Anti-dilution shares" value={plan.anti_dilution_shares.toLocaleString()} />
            )}
          </div>

          {plan.anti_dilution.length > 0 && (
            <div style={{ marginTop: 12, padding: 10, borderRadius: 8, border: "1px solid var(--border)", background: "var(--surface-2, #f6f7f5)" }}>
              <strong>Anti-dilution triggered (down round)</strong>
              {plan.anti_dilution.map((a, i) => (
                <div key={i} className="muted" style={{ fontSize: 13 }}>
                  {a.security_class} ({a.method.replace("_", " ")}): price ₹{a.orig_issue_price} → ₹
                  {a.adjusted_price}, +{a.additional_shares.toLocaleString()} shares
                </div>
              ))}
            </div>
          )}

          <h4 style={{ margin: "14px 0 6px" }}>Post-round ownership</h4>
          <StackedBar segments={barSegments} />

          <table style={{ marginTop: 14 }}>
            <thead>
              <tr>
                <th>Holder</th>
                <th>Tier</th>
                <th>Before</th>
                <th>After the round</th>
                <th>Shares after</th>
              </tr>
            </thead>
            <tbody>
              {plan.rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.name ?? "—"}</td>
                  <td className="muted">{r.tier ?? (r.type === "investor" && r.before === 0 ? "new" : "—")}</td>
                  <td>{r.before_pct}%</td>
                  <td>
                    {r.after_pct}%{delta(r.dilution_pct)}
                    {r.anti_dilution_shares > 0 && (
                      <span className="muted"> · +{r.anti_dilution_shares.toLocaleString()} AD</span>
                    )}
                  </td>
                  <td>{r.after.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {plan.excluded_instruments.length > 0 && (
            <p className="muted" style={{ fontSize: 12 }}>
              Not priced (no valuation): {plan.excluded_instruments.join(", ")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="muted" style={{ fontSize: 12 }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 700, color: "var(--heading)" }}>{value}</div>
    </div>
  );
}

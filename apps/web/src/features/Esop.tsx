import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import {
  api,
  type EsopExpense,
  type EsopGrant,
  type EsopOverview,
  type EsopScheme,
  type ExerciseWindow,
  type SecurityClass,
  type Stakeholder,
} from "../api";
import Avatar from "../components/Avatar";
import Donut from "../components/Donut";
import EmptyState from "../components/EmptyState";
import Stat from "../components/Stat";

export default function Esop({ entityId }: { entityId: string }) {
  const [schemes, setSchemes] = useState<EsopScheme[]>([]);
  const [grants, setGrants] = useState<EsopGrant[]>([]);
  const [classes, setClasses] = useState<SecurityClass[]>([]);
  const [holders, setHolders] = useState<Stakeholder[]>([]);
  const [windows, setWindows] = useState<ExerciseWindow[]>([]);
  const [overview, setOverview] = useState<EsopOverview | null>(null);
  const { error, setError, guard } = useGuard(() => load());

  // exercise-window form
  const [wName, setWName] = useState("");
  const [wOpen, setWOpen] = useState("");
  const [wClose, setWClose] = useState("");
  // Ind AS 102 expense
  const [vol, setVol] = useState("0.5");
  const [rf, setRf] = useState("0.07");
  const [life, setLife] = useState("5");
  const [expense, setExpense] = useState<EsopExpense | null>(null);

  // forms
  const [schemeName, setSchemeName] = useState("ESOP 2026");
  const [pool, setPool] = useState("100000");
  const [gScheme, setGScheme] = useState("");
  const [gEmp, setGEmp] = useState("");
  const [gType, setGType] = useState<"option" | "rsu" | "rsa">("option");
  const [gQty, setGQty] = useState("");
  const [gPrice, setGPrice] = useState("10");
  const [gDate, setGDate] = useState("2025-01-01");
  const [gFmv, setGFmv] = useState("");

  async function load() {
    try {
      const [sc, gr, cl, sh, wd, ov] = await Promise.all([
        api.listSchemes(entityId),
        api.listGrants(entityId),
        api.listSecurityClasses(entityId),
        api.listStakeholders(entityId),
        api.listExerciseWindows(entityId),
        api.esopOverview(entityId),
      ]);
      setSchemes(sc);
      setGrants(gr);
      setClasses(cl);
      setHolders(sh);
      setWindows(wd);
      setOverview(ov);
      if (!gScheme && sc.length) setGScheme(sc[0].id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  async function exercise(g: EsopGrant) {
    setError("");
    const isRsu = g.grant_type === "rsu";
    const verb = isRsu ? "Settle" : "Exercise";
    const qty = Number(prompt(`${verb} how many? (${isRsu ? "settleable" : "exercisable"}: ${g.exercisable})`, "0"));
    if (!qty) return;
    const equity = classes.find((c) => c.kind === "equity");
    if (!equity) {
      setError("Create an equity security class first (Cap Table tab).");
      return;
    }
    const cur = await api.currentValuation(entityId).catch(() => null);
    const fmv =
      prompt("FMV per share (for perquisite)? Blank uses current valuation.", cur?.fmv_per_share ?? "") ||
      "0";
    // RSUs settle for no consideration — cashless prompt only applies to options
    const cashless = !isRsu && confirm("Cashless exercise? (shares withheld to cover the strike — no cash paid)");
    try {
      await api.exerciseGrant(g.id, {
        quantity: qty,
        security_class_id: equity.id,
        fmv_per_share: fmv,
        cashless,
      });
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const employees = holders.filter((h) => h.type === "employee");

  return (
    <div>
      {error && <p className="error">{error}</p>}

      {overview && overview.pool_size > 0 && (
        <div className="card">
          <h2>ESOP overview</h2>
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Pool size" value={overview.pool_size.toLocaleString()} icon="🧩" hint="Total options across all ESOP schemes." />
            <Stat label="Granted" value={overview.granted.toLocaleString()} icon="🎁" hint="Options granted to employees so far." />
            <Stat label="Available" value={overview.available.toLocaleString()} icon="📦" hint="Unallocated pool = pool size − granted." />
            <Stat label="Pool used" value={`${overview.used_pct}%`} big icon="📊" hint="Granted as a percentage of the pool." />
            <Stat label="Grantees" value={overview.grantees} icon="👥" hint="Employees holding at least one grant." />
          </div>
          <div className="row" style={{ gap: 24, alignItems: "flex-start", marginTop: 12 }}>
            <div style={{ minWidth: 260 }}>
              <label>Pool composition</label>
              <Donut
                segments={[
                  { label: "Exercised", value: overview.pool_segments.exercised, color: "#1e6b3f" },
                  { label: "Vested (unexercised)", value: overview.pool_segments.vested_unexercised, color: "#4caf87" },
                  { label: "Unvested", value: overview.pool_segments.unvested, color: "#c9a227" },
                  { label: "Available", value: overview.pool_segments.available, color: "#d3ddd0" },
                ].filter((s) => s.value > 0)}
                centerValue={overview.pool_size.toLocaleString()}
                centerLabel="pool"
              />
            </div>
            <div style={{ flex: 1, minWidth: 240 }}>
              <label>Option states</label>
              <div className="row" style={{ gap: 8, marginTop: 4 }}>
                <Stat label="Vested" value={overview.vested.toLocaleString()} hint="Options vested to date across all grants." />
                <Stat label="Exercised" value={overview.exercised.toLocaleString()} hint="Vested options already exercised/settled into shares." />
                <Stat label="Exercisable" value={overview.exercisable.toLocaleString()} hint="Vested but not yet exercised = vested − exercised." />
                <Stat label="Unvested" value={overview.unvested.toLocaleString()} hint="Not yet vested = granted − vested." />
              </div>
              {overview.leaderboard.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <label>Employees with the highest grants</label>
                  {overview.leaderboard.map((r, i) => (
                    <div className="leaderboard-row" key={i}>
                      <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                        <Avatar name={r.name} /> {r.name}
                      </span>
                      <strong>{r.granted.toLocaleString()} options</strong>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Create scheme</h3>
          <label>Name</label>
          <input value={schemeName} onChange={(e) => setSchemeName(e.target.value)} />
          <label>Pool size (options)</label>
          <input value={pool} onChange={(e) => setPool(e.target.value)} />
          <div style={{ marginTop: 10 }}>
            <button
              onClick={guard(() =>
                api.createScheme(entityId, { name: schemeName, pool_size: Number(pool) })
              )}
            >
              Create scheme
            </button>
          </div>
          <ul className="muted" style={{ listStyle: "none", padding: 0 }}>
            {schemes.map((s) => (
              <li key={s.id} style={{ padding: "4px 0" }}>
                {s.name} — pool {s.pool_size.toLocaleString()}{" "}
                <button
                  className="secondary"
                  style={{ marginLeft: 6 }}
                  onClick={guard(async () => {
                    const docs = await api.schemePack(entityId, s.id);
                    setError("");
                    window.alert(`Generated ${docs.length} adoption documents (board resolution, EGM notice, ESOP policy) — see the Documents tab.`);
                  })}
                >
                  Adoption pack
                </button>
              </li>
            ))}
          </ul>
        </div>

        <div className="card" style={{ flex: 2 }}>
          <h3>Grant equity</h3>
          {schemes.length === 0 ? (
            <p className="muted">Create a scheme first.</p>
          ) : employees.length === 0 ? (
            <p className="muted">Add an employee stakeholder in the Cap Table tab first.</p>
          ) : (
            <>
              <div className="tabs subtabs" style={{ marginBottom: 8 }}>
                {([
                  ["option", "Options"],
                  ["rsu", "RSUs"],
                  ["rsa", "RSAs"],
                ] as const).map(([k, label]) => (
                  <button key={k} className={gType === k ? "active" : ""} onClick={() => setGType(k)}>
                    {label}
                  </button>
                ))}
              </div>
              <p className="muted" style={{ marginTop: 0 }}>
                {gType === "option" && "Options vest, then are exercised at the strike price."}
                {gType === "rsu" && "RSUs vest, then settle to shares for no payment; the full FMV is a perquisite at settlement."}
                {gType === "rsa" && "RSAs are issued as shares now (subject to repurchase of the unvested portion); the discount to FMV is a perquisite at grant."}
              </p>
              <div className="row">
                <div>
                  <label>Scheme</label>
                  <select value={gScheme} onChange={(e) => setGScheme(e.target.value)}>
                    {schemes.map((s) => (
                      <option key={s.id} value={s.id}>{s.name}</option>
                    ))}
                  </select>
                </div>
                <div>
                  <label>Employee</label>
                  <select value={gEmp} onChange={(e) => setGEmp(e.target.value)}>
                    <option value="">—</option>
                    {employees.map((h) => (
                      <option key={h.id} value={h.id}>{h.name}</option>
                    ))}
                  </select>
                </div>
              </div>
              <div className="row">
                <div>
                  <label>Quantity</label>
                  <input value={gQty} onChange={(e) => setGQty(e.target.value)} />
                </div>
                {gType !== "rsu" && (
                  <div>
                    <label>{gType === "rsa" ? "Purchase price (₹)" : "Strike (₹)"}</label>
                    <input value={gPrice} onChange={(e) => setGPrice(e.target.value)} />
                  </div>
                )}
                {gType === "rsa" && (
                  <div>
                    <label>FMV at grant (₹, blank = current)</label>
                    <input value={gFmv} onChange={(e) => setGFmv(e.target.value)} />
                  </div>
                )}
                <div>
                  <label>Grant date</label>
                  <input type="date" value={gDate} onChange={(e) => setGDate(e.target.value)} />
                </div>
              </div>
              {gType === "rsa" && !classes.some((c) => c.kind === "equity") && (
                <p className="error">Create an equity security class (Cap Table tab) before granting RSAs.</p>
              )}
              <div style={{ marginTop: 10 }}>
                <button
                  disabled={!gScheme || !gEmp || !gQty}
                  onClick={guard(async () => {
                    const equity = classes.find((c) => c.kind === "equity");
                    await api.createGrant(entityId, {
                      scheme_id: gScheme,
                      stakeholder_id: gEmp,
                      quantity: Number(gQty),
                      grant_type: gType,
                      exercise_price: gType === "rsu" ? "0" : gPrice,
                      grant_date: gDate,
                      ...(gType === "rsa"
                        ? { security_class_id: equity?.id, fmv: gFmv || "0" }
                        : {}),
                    });
                    setGQty("");
                  })}
                >
                  Grant {gType === "option" ? "options" : gType === "rsu" ? "RSUs" : "RSAs"}
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Grants (vesting as of today)</h3>
        {grants.length === 0 ? (
          <EmptyState icon="🎁" title="No grants yet" hint="Grant options, RSUs or RSAs to employees above — vesting and value tracking start automatically." />

        ) : (
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Type</th>
                <th>Granted</th>
                <th>Vested</th>
                <th>Settled / exercised</th>
                <th>Outstanding</th>
                <th>Strike</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {grants.map((g) => {
                const isRsa = g.grant_type === "rsa";
                const chipKind = g.grant_type === "rsu" ? "safe" : isRsa ? "ccps" : "option_pool";
                return (
                  <tr key={g.id}>
                    <td>{g.stakeholder_name}</td>
                    <td><span className={`sec-chip ${chipKind}`}>{g.grant_type.toUpperCase()}</span></td>
                    <td>{g.quantity.toLocaleString()}</td>
                    <td>{g.vested.toLocaleString()}</td>
                    <td>{isRsa ? "—" : g.exercised.toLocaleString()}</td>
                    <td>
                      {isRsa
                        ? `${g.unvested.toLocaleString()} unvested`
                        : g.exercisable.toLocaleString()}
                    </td>
                    <td>{g.grant_type === "rsu" ? "—" : `₹${g.exercise_price}`}</td>
                    <td>
                      {isRsa ? (
                        <span className="muted">issued at grant</span>
                      ) : (
                        <button
                          className="secondary"
                          disabled={g.exercisable <= 0}
                          onClick={() => exercise(g)}
                        >
                          {g.grant_type === "rsu" ? "Settle" : "Exercise"}
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

      <div className="card">
        <h3>Exercise windows</h3>
        <p className="muted">
          Optional: define periods when vested options may be exercised. With no windows,
          exercise is unrestricted; once you add any, requests are only allowed while a window is open.
        </p>
        <div className="row">
          <input placeholder="Window name" value={wName} onChange={(e) => setWName(e.target.value)} />
          <div>
            <label>Opens</label>
            <input type="date" value={wOpen} onChange={(e) => setWOpen(e.target.value)} />
          </div>
          <div>
            <label>Closes</label>
            <input type="date" value={wClose} onChange={(e) => setWClose(e.target.value)} />
          </div>
          <button
            style={{ flex: "0 0 auto", alignSelf: "flex-end" }}
            disabled={!wName || !wOpen || !wClose}
            onClick={guard(async () => {
              await api.createExerciseWindow(entityId, { name: wName, opens_on: wOpen, closes_on: wClose });
              setWName(""); setWOpen(""); setWClose("");
            })}
          >
            Add window
          </button>
        </div>
        {windows.length > 0 && (
          <table style={{ marginTop: 10 }}>
            <thead><tr><th>Window</th><th>Opens</th><th>Closes</th><th>State</th></tr></thead>
            <tbody>
              {windows.map((w) => (
                <tr key={w.id}>
                  <td>{w.name}</td>
                  <td>{w.opens_on}</td>
                  <td>{w.closes_on}</td>
                  <td>
                    <span className={`badge ${w.state === "open" ? "complete" : w.state === "closed" ? "" : "active"}`}>
                      {w.state}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="card">
        <h3>Share-based payment expense (Ind AS 102)</h3>
        <p className="muted">
          Grant-date fair value amortised over vesting — Black-Scholes for options, full FMV for
          RSUs/RSAs. For board and audit discussion.
        </p>
        <div className="row">
          <div><label>Volatility</label><input value={vol} onChange={(e) => setVol(e.target.value)} /></div>
          <div><label>Risk-free rate</label><input value={rf} onChange={(e) => setRf(e.target.value)} /></div>
          <div><label>Expected life (yrs)</label><input value={life} onChange={(e) => setLife(e.target.value)} /></div>
          <button
            style={{ flex: "0 0 auto", alignSelf: "flex-end" }}
            onClick={guard(async () => {
              setExpense(await api.esopExpense(entityId, { volatility: Number(vol), risk_free: Number(rf), expected_life: Number(life) }));
            })}
          >
            Compute
          </button>
          {expense && (
            <button
              className="secondary"
              style={{ flex: "0 0 auto", alignSelf: "flex-end" }}
              onClick={guard(async () => {
                await api.esopExpenseReport(entityId, { volatility: vol, risk_free: rf, expected_life: life });
                window.alert("Ind AS 102 expense report generated — see the Documents tab.");
              })}
            >
              Generate report
            </button>
          )}
        </div>
        {expense && (
          <div style={{ marginTop: 10 }}>
            <p className="muted">
              Total grant-date fair value <strong>₹{expense.totals.total_fair_value}</strong> ·
              recognised to date <strong>₹{expense.totals.recognized_to_date}</strong> ·
              unrecognised ₹{expense.totals.unrecognized}
              {expense.unpriced_grants > 0 && ` · ${expense.unpriced_grants} grant(s) unpriced (no FMV at grant date)`}
            </p>
            {expense.by_financial_year.length > 0 && (
              <table>
                <thead><tr><th>Financial year</th><th>Expense (₹)</th></tr></thead>
                <tbody>
                  {expense.by_financial_year.map((r) => (
                    <tr key={r.fy}><td>{r.fy}</td><td>{r.expense}</td></tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

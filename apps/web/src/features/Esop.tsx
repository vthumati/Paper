import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import {
  api,
  type EsopGrant,
  type EsopScheme,
  type SecurityClass,
  type Stakeholder,
} from "../api";

export default function Esop({ entityId }: { entityId: string }) {
  const [schemes, setSchemes] = useState<EsopScheme[]>([]);
  const [grants, setGrants] = useState<EsopGrant[]>([]);
  const [classes, setClasses] = useState<SecurityClass[]>([]);
  const [holders, setHolders] = useState<Stakeholder[]>([]);
  const { error, setError, guard } = useGuard(() => load());

  // forms
  const [schemeName, setSchemeName] = useState("ESOP 2026");
  const [pool, setPool] = useState("100000");
  const [gScheme, setGScheme] = useState("");
  const [gEmp, setGEmp] = useState("");
  const [gQty, setGQty] = useState("");
  const [gPrice, setGPrice] = useState("10");
  const [gDate, setGDate] = useState("2025-01-01");

  async function load() {
    try {
      const [sc, gr, cl, sh] = await Promise.all([
        api.listSchemes(entityId),
        api.listGrants(entityId),
        api.listSecurityClasses(entityId),
        api.listStakeholders(entityId),
      ]);
      setSchemes(sc);
      setGrants(gr);
      setClasses(cl);
      setHolders(sh);
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
    const qty = Number(prompt(`Exercise how many? (exercisable: ${g.exercisable})`, "0"));
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
    const cashless = confirm("Cashless exercise? (shares withheld to cover the strike — no cash paid)");
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
          <ul className="muted">
            {schemes.map((s) => (
              <li key={s.id}>
                {s.name} — pool {s.pool_size.toLocaleString()}
              </li>
            ))}
          </ul>
        </div>

        <div className="card" style={{ flex: 2 }}>
          <h3>Grant options</h3>
          {schemes.length === 0 ? (
            <p className="muted">Create a scheme first.</p>
          ) : employees.length === 0 ? (
            <p className="muted">Add an employee stakeholder in the Cap Table tab first.</p>
          ) : (
            <>
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
                <div>
                  <label>Strike (₹)</label>
                  <input value={gPrice} onChange={(e) => setGPrice(e.target.value)} />
                </div>
                <div>
                  <label>Grant date</label>
                  <input type="date" value={gDate} onChange={(e) => setGDate(e.target.value)} />
                </div>
              </div>
              <div style={{ marginTop: 10 }}>
                <button
                  disabled={!gScheme || !gEmp || !gQty}
                  onClick={guard(async () => {
                    await api.createGrant(entityId, {
                      scheme_id: gScheme,
                      stakeholder_id: gEmp,
                      quantity: Number(gQty),
                      exercise_price: gPrice,
                      grant_date: gDate,
                    });
                    setGQty("");
                  })}
                >
                  Grant
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Grants (vesting as of today)</h3>
        {grants.length === 0 ? (
          <p className="muted">No grants yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Employee</th>
                <th>Granted</th>
                <th>Vested</th>
                <th>Exercised</th>
                <th>Exercisable</th>
                <th>Strike</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {grants.map((g) => (
                <tr key={g.id}>
                  <td>{g.stakeholder_name}</td>
                  <td>{g.quantity.toLocaleString()}</td>
                  <td>{g.vested.toLocaleString()}</td>
                  <td>{g.exercised.toLocaleString()}</td>
                  <td>{g.exercisable.toLocaleString()}</td>
                  <td>₹{g.exercise_price}</td>
                  <td>
                    <button
                      className="secondary"
                      disabled={g.exercisable <= 0}
                      onClick={() => exercise(g)}
                    >
                      Exercise
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}

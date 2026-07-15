import { useEffect, useState } from "react";
import {
  api,
  downloadFile,
  type CapTable as CapTableT,
  type CapTableRow,
  type SecurityClass,
  type Stakeholder,
} from "../api";
import Avatar from "../components/Avatar";
import SecChip from "../components/SecChip";
import StackedBar from "../components/StackedBar";
import DownRoundCalc from "./DownRoundCalc";
import FullyDilutedView from "./FullyDiluted";
import ImportCapTable from "./ImportCapTable";

type Pivot = "positions" | "holder" | "class";

/** Re-slice the per-(stakeholder, class) positions by stakeholder or by
 * security class (Eqvista's Class | Grant | Shareholder pivot). */
function aggregate(rows: CapTableRow[], by: "holder" | "class") {
  const agg = new Map<
    string,
    { name: string | null; sub: string | null; quantity: number; invested: number; pct: number }
  >();
  for (const r of rows) {
    const key = by === "holder" ? r.stakeholder_id : r.security_class_id;
    const row = agg.get(key) ?? {
      name: by === "holder" ? r.stakeholder_name : r.security_class,
      sub: by === "holder" ? r.stakeholder_type : r.kind,
      quantity: 0,
      invested: 0,
      pct: 0,
    };
    row.quantity += r.quantity;
    row.invested += Number(r.amount_invested);
    row.pct += r.ownership_pct;
    agg.set(key, row);
  }
  return [...agg.values()].sort((a, b) => b.quantity - a.quantity);
}

export default function CapTable({
  entityId,
  refreshKey,
  features,
}: {
  entityId: string;
  refreshKey?: number;
  features?: Record<string, boolean>;
}) {
  const feat = (k: string) => !features || features[k] !== false;
  const [classes, setClasses] = useState<SecurityClass[]>([]);
  const [holders, setHolders] = useState<Stakeholder[]>([]);
  const [capTable, setCapTable] = useState<CapTableT | null>(null);
  const [view, setView] = useState<"issued" | "fd">("issued");
  const [pivot, setPivot] = useState<Pivot>("positions");
  const [error, setError] = useState("");

  // form state
  const [scName, setScName] = useState("Equity");
  const [scKind, setScKind] = useState("equity");
  const [scPref, setScPref] = useState("0");
  const [scPart, setScPart] = useState(false);
  const [scAd, setScAd] = useState("none");
  const [scOip, setScOip] = useState("");
  const [shName, setShName] = useState("");
  const [shType, setShType] = useState("founder");
  const [iSc, setISc] = useState("");
  const [iSh, setISh] = useState("");
  const [iQty, setIQty] = useState("");
  const [iPrice, setIPrice] = useState("");

  async function loadAll() {
    try {
      const [c, h, ct] = await Promise.all([
        api.listSecurityClasses(entityId),
        api.listStakeholders(entityId),
        api.capTable(entityId),
      ]);
      setClasses(c);
      setHolders(h);
      setCapTable(ct);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    loadAll();
  }, [entityId, refreshKey]);

  const wrap = (fn: () => Promise<unknown>) => async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await fn();
      await loadAll();
    } catch (err) {
      setError((err as Error).message);
    }
  };

  return (
    <div>
      {error && <p className="error">{error}</p>}

      <div className="card">
        <h2>
          Cap table
          {feat("fully_diluted") && (
            <>
              {" "}
              <button
                className={view === "issued" ? "" : "secondary"}
                style={{ marginLeft: 8 }}
                onClick={() => setView("issued")}
              >
                Issued
              </button>{" "}
              <button
                className={view === "fd" ? "" : "secondary"}
                onClick={() => setView("fd")}
              >
                Fully diluted
              </button>
            </>
          )}
          <details className="actions-menu">
            <summary>Actions ▾</summary>
            <div className="actions-list">
              <button
                className="secondary"
                onClick={() => downloadFile(`/entities/${entityId}/cap-table.csv`, "cap-table.csv")}
              >
                Download cap table (CSV)
              </button>
              <button
                className="secondary"
                onClick={() => api.downloadImportTemplate(entityId)}
              >
                Import template (CSV)
              </button>
            </div>
          </details>
        </h2>
        {view === "issued" ? (
          !capTable || capTable.holders.length === 0 ? (
            <p className="muted">No issuances yet. Add a security class, a stakeholder, then issue shares.</p>
          ) : (
            <>
              <p className="muted">
                Total shares: <strong>{capTable.total_shares.toLocaleString()}</strong> · Total
                invested: <strong>₹{capTable.total_invested}</strong>
              </p>
              <div style={{ margin: "12px 0 16px" }}>
                <StackedBar
                  segments={aggregate(capTable.holders, "class").map((r) => ({
                    label: r.name ?? "?",
                    value: r.quantity,
                  }))}
                />
              </div>
              <div style={{ marginBottom: 8 }}>
                {(
                  [
                    ["positions", "Positions"],
                    ["holder", "By stakeholder"],
                    ["class", "By class"],
                  ] as [Pivot, string][]
                ).map(([k, label]) => (
                  <button
                    key={k}
                    className={pivot === k ? "" : "secondary"}
                    style={{ marginRight: 6 }}
                    onClick={() => setPivot(k)}
                  >
                    {label}
                  </button>
                ))}
              </div>
              {pivot === "positions" ? (
                <table>
                  <thead>
                    <tr>
                      <th>Stakeholder</th>
                      <th>Type</th>
                      <th>Security</th>
                      <th>Quantity</th>
                      <th>Invested (₹)</th>
                      <th>Ownership %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {capTable.holders.map((r, i) => (
                      <tr key={i}>
                        <td>
                          <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                            <Avatar name={r.stakeholder_name} />
                            {r.stakeholder_name}
                          </span>
                        </td>
                        <td>{r.stakeholder_type}</td>
                        <td><SecChip name={r.security_class} kind={r.kind} /></td>
                        <td>{r.quantity.toLocaleString()}</td>
                        <td>{r.amount_invested}</td>
                        <td>{r.ownership_pct}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <table>
                  <thead>
                    <tr>
                      <th>{pivot === "holder" ? "Stakeholder" : "Security"}</th>
                      {pivot === "holder" && <th>Type</th>}
                      <th>Quantity</th>
                      <th>Invested (₹)</th>
                      <th>Ownership %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {aggregate(capTable.holders, pivot).map((r, i) => (
                      <tr key={i}>
                        <td>
                          {pivot === "class" ? (
                            <SecChip name={r.name} kind={r.sub} />
                          ) : (
                            <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                              <Avatar name={r.name} />
                              {r.name}
                            </span>
                          )}
                        </td>
                        {pivot === "holder" && <td>{r.sub}</td>}
                        <td>{r.quantity.toLocaleString()}</td>
                        <td>{r.invested.toFixed(2)}</td>
                        <td>{Math.round(r.pct * 10000) / 10000}%</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )
        ) : (
          <FullyDilutedView entityId={entityId} refreshKey={refreshKey} />
        )}
      </div>

      <div className="row">
        <div className="card">
          <h3>Security class</h3>
          <form
            onSubmit={wrap(() =>
              api.createSecurityClass(entityId, {
                name: scName,
                kind: scKind,
                par_value: "10",
                pref_multiple: scPref || "0",
                participating: scPart,
                anti_dilution: scAd,
                orig_issue_price: scOip || null,
              })
            )}
          >
            <label>Name</label>
            <input value={scName} onChange={(e) => setScName(e.target.value)} />
            <label>Kind</label>
            <select value={scKind} onChange={(e) => setScKind(e.target.value)}>
              {["equity", "ccps", "ccd", "option_pool", "safe", "warrant"].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
            <label>Liquidation pref (× invested; 0 = common)</label>
            <input value={scPref} onChange={(e) => setScPref(e.target.value)} />
            <label style={{ display: "flex", alignItems: "center", gap: 6 }}>
              <input type="checkbox" style={{ width: "auto" }} checked={scPart} onChange={(e) => setScPart(e.target.checked)} />
              participating
            </label>
            {feat("anti_dilution") && (
              <>
                <label>Anti-dilution</label>
                <select value={scAd} onChange={(e) => setScAd(e.target.value)}>
                  <option value="none">none</option>
                  <option value="broad_based">broad-based weighted average</option>
                  <option value="full_ratchet">full ratchet</option>
                </select>
                {scAd !== "none" && (
                  <>
                    <label>Original issue price (₹/share)</label>
                    <input value={scOip} onChange={(e) => setScOip(e.target.value)} placeholder="e.g. 100" />
                  </>
                )}
              </>
            )}
            <div style={{ marginTop: 10 }}><button>Add class</button></div>
          </form>
          <ul className="muted">
            {classes.map((c) => <li key={c.id}>{c.name} ({c.kind})</li>)}
          </ul>
        </div>

        <div className="card">
          <h3>Stakeholder</h3>
          <form onSubmit={wrap(() => api.createStakeholder(entityId, { name: shName, type: shType }))}>
            <label>Name</label>
            <input value={shName} onChange={(e) => setShName(e.target.value)} required />
            <label>Type</label>
            <select value={shType} onChange={(e) => setShType(e.target.value)}>
              {["founder", "investor", "employee", "entity"].map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
            <div style={{ marginTop: 10 }}><button>Add stakeholder</button></div>
          </form>
          <ul className="muted">
            {holders.map((h) => <li key={h.id}>{h.name} ({h.type})</li>)}
          </ul>
        </div>
      </div>

      <div className="card">
        <h3>Issue shares</h3>
        <form
          onSubmit={wrap(() =>
            api.createIssuance(entityId, {
              security_class_id: iSc,
              stakeholder_id: iSh,
              quantity: Number(iQty),
              price_per_unit: iPrice || "0",
              issue_date: new Date().toISOString().slice(0, 10),
            })
          )}
        >
          <div className="row">
            <div>
              <label>Security class</label>
              <select value={iSc} onChange={(e) => setISc(e.target.value)} required>
                <option value="">—</option>
                {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </div>
            <div>
              <label>Stakeholder</label>
              <select value={iSh} onChange={(e) => setISh(e.target.value)} required>
                <option value="">—</option>
                {holders.map((h) => <option key={h.id} value={h.id}>{h.name}</option>)}
              </select>
            </div>
            <div>
              <label>Quantity</label>
              <input type="number" value={iQty} onChange={(e) => setIQty(e.target.value)} required />
            </div>
            <div>
              <label>Price/unit (₹)</label>
              <input value={iPrice} onChange={(e) => setIPrice(e.target.value)} placeholder="0" />
            </div>
          </div>
          <div style={{ marginTop: 10 }}><button>Record issuance</button></div>
        </form>
      </div>

      <ImportCapTable entityId={entityId} onApplied={loadAll} />

      {feat("anti_dilution") && <DownRoundCalc entityId={entityId} classes={classes} />}
    </div>
  );
}

import { useEffect, useState } from "react";
import { fmtMoney } from "../lib/format";
import { useGuard } from "../hooks";
import { api, type Entitlement, type RightsIssue, type SecurityClass } from "../api";

export default function RightsIssues({
  entityId,
  onChanged,
}: {
  entityId: string;
  onChanged?: () => void;
}) {
  const [classes, setClasses] = useState<SecurityClass[]>([]);
  const [issues, setIssues] = useState<RightsIssue[]>([]);
  const [selected, setSelected] = useState<RightsIssue | null>(null);
  const [ent, setEnt] = useState<Entitlement[]>([]);
  const [subQty, setSubQty] = useState<Record<string, string>>({});
  const { error, setError, guard } = useGuard();
  const [note, setNote] = useState("");

  // create form
  const [sc, setSc] = useState("");
  const [num, setNum] = useState("1");
  const [den, setDen] = useState("2");
  const [price, setPrice] = useState("");

  async function load() {
    try {
      const [c, i] = await Promise.all([
        api.listSecurityClasses(entityId),
        api.listRightsIssues(entityId),
      ]);
      setClasses(c);
      setIssues(i);
      if (!sc && c.length) setSc(c[0].id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  async function select(ri: RightsIssue) {
    setNote("");
    setSelected(ri);
    setEnt((await api.rightsEntitlements(ri.id)).entitlements);
  }

  return (
    <div className="card">
      <h3>Rights issue</h3>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      <div className="row">
        <select value={sc} onChange={(e) => setSc(e.target.value)}>
          {classes.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <input placeholder="num" value={num} onChange={(e) => setNum(e.target.value)} />
        <input placeholder="den" value={den} onChange={(e) => setDen(e.target.value)} />
        <input placeholder="Price/share" value={price} onChange={(e) => setPrice(e.target.value)} />
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!sc || !num || !den}
          onClick={guard(async () => {
            await api.createRightsIssue(entityId, {
              security_class_id: sc,
              ratio_num: Number(num),
              ratio_den: Number(den),
              price_per_unit: price || "0",
            });
            await load();
          })}
        >
          Open rights issue
        </button>
      </div>
      <p className="muted">Ratio num:den = new shares per shares held (e.g. 1:2).</p>

      {issues.map((ri) => (
        <div
          key={ri.id}
          className={`list-item ${selected?.id === ri.id ? "selected" : ""}`}
          onClick={() => select(ri)}
        >
          {ri.ratio_num}:{ri.ratio_den} @ {fmtMoney(ri.price_per_unit)}{" "}
          <span className={`badge ${ri.status === "closed" ? "complete" : ""}`}>{ri.status}</span>
        </div>
      ))}

      {selected && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Holder</th><th>Held</th><th>Entitled</th><th>Subscribed</th>{selected.status === "open" && <th></th>}</tr>
          </thead>
          <tbody>
            {ent.map((e) => (
              <tr key={e.stakeholder_id}>
                <td>{e.stakeholder_name}</td>
                <td>{e.held.toLocaleString()}</td>
                <td>{e.entitled.toLocaleString()}</td>
                <td>{e.subscribed.toLocaleString()}</td>
                {selected.status === "open" && (
                  <td>
                    <input
                      style={{ width: 80 }}
                      placeholder="qty"
                      value={subQty[e.stakeholder_id] ?? ""}
                      onChange={(ev) => setSubQty({ ...subQty, [e.stakeholder_id]: ev.target.value })}
                    />
                    <button
                      className="secondary"
                      onClick={guard(async () => {
                        await api.subscribeRights(selected.id, {
                          stakeholder_id: e.stakeholder_id,
                          quantity: Number(subQty[e.stakeholder_id] || 0),
                        });
                        setSubQty({ ...subQty, [e.stakeholder_id]: "" });
                        await select(selected);
                      })}
                    >
                      Subscribe
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {selected && selected.status === "open" && (
        <div style={{ marginTop: 10 }}>
          <button
            onClick={guard(async () => {
              const r = await api.closeRights(selected.id);
              setNote(`Closed: ${r.issued_shares.toLocaleString()} shares issued, ₹${r.amount_raised} raised.`);
              await load();
              setSelected(null);
              onChanged?.();
            })}
          >
            Close rights issue
          </button>
        </div>
      )}
    </div>
  );
}

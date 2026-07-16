import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { useGuard } from "../hooks";
import { api, type Contract, type Counterparty } from "../api";

const STATUSES = ["draft", "active", "expired", "terminated"];

export default function Contracts({ entityId }: { entityId: string }) {
  const [counterparties, setCounterparties] = useState<Counterparty[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const { error, setError, guard } = useGuard(() => load());
  const [note, setNote] = useState("");

  // forms
  const [cpName, setCpName] = useState("");
  const [cpKind, setCpKind] = useState("customer");
  const [cId, setCId] = useState("");
  const [title, setTitle] = useState("");
  const [value, setValue] = useState("");
  const [renewal, setRenewal] = useState("");

  async function load() {
    try {
      const [cp, c] = await Promise.all([
        api.listCounterparties(entityId),
        api.listContracts(entityId),
      ]);
      setCounterparties(cp);
      setContracts(c);
      if (!cId && cp.length) setCId(cp[0].id);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  function renewalCell(c: Contract) {
    if (!c.renewal_date) return <span className="muted">—</span>;
    if (c.renewal_overdue)
      return (
        <span>
          {c.renewal_date} <span className="badge active">overdue</span>
        </span>
      );
    if (c.days_to_renewal !== null && c.days_to_renewal <= 30)
      return (
        <span>
          {c.renewal_date} <span className="badge active">{c.days_to_renewal}d</span>
        </span>
      );
    return <span>{c.renewal_date}</span>;
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Add counterparty</h3>
          <input placeholder="Name" value={cpName} onChange={(e) => setCpName(e.target.value)} />
          <label>Kind</label>
          <select value={cpKind} onChange={(e) => setCpKind(e.target.value)}>
            <option value="customer">Customer</option>
            <option value="vendor">Vendor</option>
            <option value="partner">Partner</option>
          </select>
          <div style={{ marginTop: 10 }}>
            <button
              disabled={!cpName}
              onClick={guard(async () => {
                await api.addCounterparty(entityId, { name: cpName, kind: cpKind });
                setCpName("");
              })}
            >
              Add
            </button>
          </div>
        </div>

        <div className="card" style={{ flex: 2 }}>
          <h3>New contract</h3>
          {counterparties.length === 0 ? (
            <p className="muted">Add a counterparty first.</p>
          ) : (
            <>
              <div className="row">
                <div>
                  <label>Counterparty</label>
                  <select value={cId} onChange={(e) => setCId(e.target.value)}>
                    {counterparties.map((cp) => (
                      <option key={cp.id} value={cp.id}>{cp.name} ({cp.kind})</option>
                    ))}
                  </select>
                </div>
                <div><label>Title</label><input value={title} onChange={(e) => setTitle(e.target.value)} /></div>
                <div><label>Value (₹)</label><input value={value} onChange={(e) => setValue(e.target.value)} /></div>
                <div><label>Renewal date</label><input type="date" value={renewal} onChange={(e) => setRenewal(e.target.value)} /></div>
              </div>
              <div style={{ marginTop: 10 }}>
                <button
                  disabled={!cId || !title}
                  onClick={guard(async () => {
                    await api.addContract(entityId, {
                      counterparty_id: cId,
                      title,
                      type: "msa",
                      value: value || null,
                      renewal_date: renewal || null,
                    });
                    setTitle(""); setValue(""); setRenewal("");
                  })}
                >
                  Add contract
                </button>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="card">
        <h3>Contracts</h3>
        {contracts.length === 0 ? (
          <EmptyState icon="📑" title="No contracts yet" hint="Add a customer, vendor or partner contract to track its value and renewal date." />
        ) : (
          <table>
            <thead>
              <tr><th>Title</th><th>Counterparty</th><th>Value</th><th>Renewal</th><th>Status</th><th></th></tr>
            </thead>
            <tbody>
              {contracts.map((c) => (
                <tr key={c.id}>
                  <td>{c.title}</td>
                  <td>{c.counterparty_name} <span className="muted">({c.counterparty_kind})</span></td>
                  <td>{c.value ? `₹${c.value}` : "—"}</td>
                  <td>{renewalCell(c)}</td>
                  <td>
                    <select
                      value={c.status}
                      onChange={(ev) => guard(() => api.updateContractStatus(c.id, { status: ev.target.value }))()}
                    >
                      {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                    </select>
                  </td>
                  <td>
                    {c.document_id ? (
                      <span className="muted">doc ✓</span>
                    ) : (
                      <button
                        className="secondary"
                        onClick={guard(async () => {
                          await api.generateContractDoc(c.id, "msa");
                          setNote("Contract document generated (see Files).");
                        })}
                      >
                        Generate MSA
                      </button>
                    )}
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

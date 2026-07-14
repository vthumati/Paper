import { useEffect, useState } from "react";
import { useGuard } from "../hooks";
import {
  api,
  ApiError,
  type CoInvestor,
  type Entity,
  type SecurityClass,
  type SPV,
  type SPVSummary,
} from "../api";

export default function Spv({ entityId }: { entityId: string }) {
  const [spv, setSpv] = useState<SPV | null>(null);
  const [coInvestors, setCoInvestors] = useState<CoInvestor[]>([]);
  const [summary, setSummary] = useState<SPVSummary | null>(null);
  const [portcoOptions, setPortcoOptions] = useState<Entity[]>([]);
  const [portcoClasses, setPortcoClasses] = useState<SecurityClass[]>([]);
  const { error, setError, guard } = useGuard(() => load());

  // forms
  const [sponsor, setSponsor] = useState("");
  const [target, setTarget] = useState("");
  const [portco, setPortco] = useState("");
  const [ciName, setCiName] = useState("");
  const [ciCommit, setCiCommit] = useState("");
  const [invSc, setInvSc] = useState("");
  const [invQty, setInvQty] = useState("");
  const [invPrice, setInvPrice] = useState("");

  async function load() {
    try {
      const entity = await api.getEntity(entityId);
      const peers = await api.listEntities(entity.tenant_id);
      setPortcoOptions(peers.filter((e) => e.id !== entityId));
      try {
        const s = await api.getSPV(entityId);
        setSpv(s);
        const [ci, sum] = await Promise.all([
          api.listCoInvestors(s.id),
          api.spvSummary(s.id),
        ]);
        setCoInvestors(ci);
        setSummary(sum);
        if (s.portco_entity_id) {
          setPortcoClasses(await api.listSecurityClasses(s.portco_entity_id));
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) setSpv(null);
        else throw e;
      }
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load();
  }, [entityId]);

  if (!spv) {
    return (
      <div className="card">
        {error && <p className="error">{error}</p>}
        <h2>Set up SPV</h2>
        <label>Sponsor</label>
        <input value={sponsor} onChange={(e) => setSponsor(e.target.value)} />
        <label>Target company (name)</label>
        <input value={target} onChange={(e) => setTarget(e.target.value)} />
        <label>Portfolio company on Paper (optional — enables the cap-table sweep)</label>
        <select value={portco} onChange={(e) => setPortco(e.target.value)}>
          <option value="">— none —</option>
          {portcoOptions.map((e) => (
            <option key={e.id} value={e.id}>{e.name}</option>
          ))}
        </select>
        <div style={{ marginTop: 10 }}>
          <button
            disabled={!sponsor || !target}
            onClick={guard(() =>
              api.createSPV(entityId, {
                sponsor,
                target_company: target,
                portco_entity_id: portco || null,
              })
            )}
          >
            Create SPV
          </button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <h2>
          SPV — {spv.target_company} <span className="badge">{spv.structure}</span>
        </h2>
        {summary && (
          <p className="muted">
            {summary.co_investor_count} co-investors · Committed ₹{summary.committed} ·
            Contributed ₹{summary.contributed}
          </p>
        )}
      </div>

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Add co-investor</h3>
          <label>Name</label>
          <input value={ciName} onChange={(e) => setCiName(e.target.value)} />
          <label>Commitment (₹)</label>
          <input value={ciCommit} onChange={(e) => setCiCommit(e.target.value)} />
          <div style={{ marginTop: 10 }}>
            <button
              disabled={!ciName || !ciCommit}
              onClick={guard(async () => {
                await api.addCoInvestor(spv.id, { name: ciName, commitment: ciCommit });
                setCiName("");
                setCiCommit("");
              })}
            >
              Add
            </button>
          </div>
        </div>

        {spv.portco_entity_id && (
          <div className="card" style={{ flex: 1 }}>
            <h3>Invest in portco</h3>
            <p className="muted">Sweeps a combined holding into the portco cap table.</p>
            <label>Security class</label>
            <select value={invSc} onChange={(e) => setInvSc(e.target.value)}>
              <option value="">—</option>
              {portcoClasses.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <div className="row">
              <div>
                <label>Quantity</label>
                <input value={invQty} onChange={(e) => setInvQty(e.target.value)} />
              </div>
              <div>
                <label>Price/unit (₹)</label>
                <input value={invPrice} onChange={(e) => setInvPrice(e.target.value)} />
              </div>
            </div>
            <div style={{ marginTop: 10 }}>
              <button
                disabled={!invSc || !invQty}
                onClick={guard(async () => {
                  await api.spvInvest(spv.id, {
                    security_class_id: invSc,
                    quantity: Number(invQty),
                    price_per_unit: invPrice || "0",
                  });
                  setInvQty("");
                  setInvPrice("");
                })}
              >
                Invest
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="card">
        <h3>Co-investors</h3>
        {coInvestors.length === 0 ? (
          <p className="muted">None yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Commitment</th>
                <th>Contributed</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {coInvestors.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>₹{c.commitment}</td>
                  <td>₹{c.contributed}</td>
                  <td>
                    {c.paid ? (
                      <span className="badge complete">paid</span>
                    ) : (
                      <button
                        className="secondary"
                        onClick={guard(() => api.contributeCoInvestor(spv.id, c.id))}
                      >
                        Mark contributed
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

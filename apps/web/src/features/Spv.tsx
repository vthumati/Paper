import { useEffect, useState } from "react";
import { fmtMoney } from "../lib/format";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import Stepper from "../components/Stepper";
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
  const [ciEmail, setCiEmail] = useState("");
  const [ciCommit, setCiCommit] = useState("");
  const [carry, setCarry] = useState("");
  const [minTicket, setMinTicket] = useState("");
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
      <div>
        <PageHeader
          icon="🤝"
          title="Set up SPV"
          subtitle="Pool co-investors into one vehicle"
        />
        <div className="card">
        {error && <p className="error">{error}</p>}
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
      </div>
    );
  }

  return (
    <div>
      {error && <p className="error">{error}</p>}
      <PageHeader
        icon="🤝"
        title={`SPV — ${spv.target_company}`}
        subtitle="Co-investment vehicle"
        right={<span className="badge">{spv.structure}</span>}
      />
      <div className="card">
        {summary && (
          <p className="muted">
            {summary.co_investor_count} co-investors ({summary.by_status.invited} invited ·{" "}
            {summary.by_status.committed} committed · {summary.by_status.funded} funded) ·
            Committed {fmtMoney(summary.committed)} · Contributed {fmtMoney(summary.contributed)}
          </p>
        )}
        <p className="muted">
          Deal terms: carry {(Number(spv.carry_pct) * 100).toFixed(1)}% · minimum ticket ₹
          {spv.min_ticket}
        </p>
      </div>

      <div className="row">
        <div className="card" style={{ flex: 1 }}>
          <h3>Deal terms</h3>
          <p className="muted">
            Sets the SPV's economics and provisions its fund profile (carry, no hurdle or
            management fee).
          </p>
          <div className="row">
            <div>
              <label>Carry (%)</label>
              <input value={carry} onChange={(e) => setCarry(e.target.value)} placeholder="20" />
            </div>
            <div>
              <label>Minimum ticket (₹)</label>
              <input value={minTicket} onChange={(e) => setMinTicket(e.target.value)} placeholder="500000" />
            </div>
          </div>
          <div style={{ marginTop: 10 }}>
            <button
              disabled={!carry}
              onClick={guard(async () => {
                await api.setSPVTerms(spv.id, {
                  carry_pct: (Number(carry) / 100).toString(),
                  min_ticket: minTicket || "0",
                });
                setCarry("");
                setMinTicket("");
              })}
            >
              Save terms
            </button>
          </div>
        </div>

        <div className="card" style={{ flex: 1 }}>
          <h3>Invite co-investor</h3>
          <label>Name</label>
          <input value={ciName} onChange={(e) => setCiName(e.target.value)} />
          <label>Email (they commit from their portal)</label>
          <input value={ciEmail} onChange={(e) => setCiEmail(e.target.value)} />
          <label>Commitment (₹ — leave blank to let them commit)</label>
          <input value={ciCommit} onChange={(e) => setCiCommit(e.target.value)} />
          <div style={{ marginTop: 10 }}>
            <button
              disabled={!ciName || (!ciCommit && !ciEmail)}
              onClick={guard(async () => {
                await api.addCoInvestor(spv.id, {
                  name: ciName,
                  email: ciEmail || null,
                  commitment: ciCommit || "0",
                });
                setCiName("");
                setCiEmail("");
                setCiCommit("");
              })}
            >
              {ciCommit ? "Add" : "Invite"}
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
          <EmptyState icon="🤝" title="No co-investors yet" hint="Invite backers by email — they commit from their portal and the deal funds when commitments land." />
        ) : (
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Email</th>
                <th>Status</th>
                <th>Commitment</th>
                <th>Contributed</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {coInvestors.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td>{c.email ?? "—"}</td>
                  <td>
                    <Stepper
                      steps={["invited", "committed", "funded"].map((s, i) => {
                        const at = ["invited", "committed", "funded"].indexOf(c.status);
                        return {
                          label: s,
                          state: i < at ? "done" : i === at ? (s === "funded" ? "done" : "active") : "todo",
                        };
                      })}
                    />
                  </td>
                  <td>{fmtMoney(c.commitment)}</td>
                  <td>{fmtMoney(c.contributed)}</td>
                  <td>
                    {c.status === "committed" && (
                      <button
                        className="secondary"
                        onClick={guard(() => api.contributeCoInvestor(spv.id, c.id))}
                      >
                        Mark funded
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

import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import TeardownDialog from "../components/TeardownDialog";
import { useNavigate, useParams } from "react-router-dom";
import IncorporationWizard from "../features/IncorporationWizard";
import { api, type Entity } from "../api";

export default function Entities() {
  const { tenantId = "" } = useParams();
  const nav = useNavigate();
  const [entities, setEntities] = useState<Entity[]>([]);
  const [name, setName] = useState("");
  const [type, setType] = useState("pvt_ltd");
  const [error, setError] = useState("");
  const [tearing, setTearing] = useState<Entity | null>(null);

  const load = () =>
    api.listEntities(tenantId).then(setEntities).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, [tenantId]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await api.createEntity(tenantId, { name, type });
      setName("");
      load();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div>
      <p className="muted">
        <a href="#" onClick={(e) => { e.preventDefault(); nav("/"); }}>
          ← Workspaces
        </a>
      </p>
      <h1>Legal entities</h1>
      <p className="muted" style={{ marginTop: 4 }}>Incorporate a new company or manage the entities in this workspace.</p>

      <IncorporationWizard tenantId={tenantId} onRegistered={load} />

      <div className="card">
        <h2>Add an existing entity</h2>
        <form onSubmit={create}>
          <div className="row">
            <div>
              <label>Name</label>
              <input value={name} onChange={(e) => setName(e.target.value)} required />
            </div>
            <div style={{ flex: "0 0 160px" }}>
              <label>Type</label>
              <select value={type} onChange={(e) => setType(e.target.value)}>
                <option value="pvt_ltd">Pvt Ltd</option>
                <option value="llp">LLP</option>
                <option value="opc">OPC</option>
                <option value="fund">Fund</option>
                <option value="spv">SPV</option>
              </select>
            </div>
          </div>
          {error && <p className="error">{error}</p>}
          <div style={{ marginTop: 12 }}>
            <button type="submit">Add</button>
          </div>
        </form>
      </div>

      <div className="card">
        <h2>Entities</h2>
        {entities.length === 0 && (
          <EmptyState icon="🏢" title="No entities yet" hint="Incorporate a company or add an existing entity above to open its workspace." />
        )}
        {entities.map((e) => (
          <div
            key={e.id}
            className="list-item"
            style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}
            onClick={() => nav(`/entities/${e.id}`)}
          >
            <span>
              <strong>{e.name}</strong> <span className="badge">{e.type}</span>
              {e.cin && <span className="muted"> · CIN {e.cin}</span>}
            </span>
            <button
              className="secondary"
              style={{ flex: "0 0 auto" }}
              title="Delete this entity and all its data"
              onClick={(ev) => {
                ev.stopPropagation();
                setTearing(e);
              }}
            >
              Delete
            </button>
          </div>
        ))}
      </div>

      {tearing && (
        <TeardownDialog
          kind="entity"
          id={tearing.id}
          name={tearing.name}
          onClose={() => setTearing(null)}
          onDone={() => {
            setTearing(null);
            load();
          }}
        />
      )}
    </div>
  );
}

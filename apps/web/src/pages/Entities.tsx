import { useEffect, useState } from "react";
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
          ← Organisations
        </a>
      </p>
      <h1>Legal entities</h1>

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
        {entities.length === 0 && <p className="muted">No entities yet.</p>}
        {entities.map((e) => (
          <div key={e.id} className="list-item" onClick={() => nav(`/entities/${e.id}`)}>
            <strong>{e.name}</strong> <span className="badge">{e.type}</span>
            {e.cin && <span className="muted"> · CIN {e.cin}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

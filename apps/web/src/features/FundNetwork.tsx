import { useEffect, useState } from "react";
import { api, type FirmNetwork } from "../api";
import Avatar from "../components/Avatar";
import StrengthPie from "../components/StrengthPie";

/** Firm network directory (4Degrees-style "who do we know at X"): every
 * contact across deals and the LP fundraise in one searchable roster, with
 * relationship strength and last touch. Read-only derivation. */
export default function FundNetwork({ fundId }: { fundId: string }) {
  const [net, setNet] = useState<FirmNetwork | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    api.fundNetwork(fundId).then(setNet).catch((e) => setError(e.message));
  }, [fundId]);

  if (!net || net.count === 0) return null;
  const needle = q.trim().toLowerCase();
  const people = needle
    ? net.people.filter(
        (p) =>
          p.name.toLowerCase().includes(needle) ||
          (p.role ?? "").toLowerCase().includes(needle) ||
          (p.email ?? "").toLowerCase().includes(needle) ||
          p.links.some((l) => l.toLowerCase().includes(needle))
      )
    : net.people;

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>🕸️</span> Network
        <span className="badge">{net.count} people</span>
        <input
          placeholder="Who do we know at…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          style={{ marginLeft: "auto", maxWidth: 240 }}
        />
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Everyone the fund knows — deal contacts and LP prospects in one roster, ranked by
        relationship strength from logged touches.
      </p>
      {error && <p className="error">{error}</p>}
      {people.length === 0 ? (
        <p className="muted">No one matches “{q}”.</p>
      ) : (
        <table>
          <thead>
            <tr><th>Person</th><th>Role / firm</th><th>Connected via</th><th>Strength</th><th>Last touch</th></tr>
          </thead>
          <tbody>
            {people.map((p) => (
              <tr key={p.email ?? p.name}>
                <td>
                  <Avatar name={p.name} /> {p.name}
                  {p.email && <span className="muted" style={{ fontSize: 12 }}> · {p.email}</span>}
                </td>
                <td>{p.role ?? <span className="muted">—</span>}</td>
                <td>
                  {p.links.map((l) => (
                    <span key={l} className="badge" style={{ marginRight: 4 }}>{l}</span>
                  ))}
                </td>
                <td><StrengthPie value={p.strength} /> <span className="num">{p.strength}</span></td>
                <td>{p.last_touch ?? <span className="muted">never</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

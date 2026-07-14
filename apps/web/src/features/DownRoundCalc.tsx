import { useState } from "react";
import { api, type AntiDilutionPreview, type SecurityClass } from "../api";

/** Anti-dilution what-if: adjusted conversion price/ratio for a down round. */
export default function DownRoundCalc({
  entityId,
  classes,
}: {
  entityId: string;
  classes: SecurityClass[];
}) {
  const protectedClasses = classes.filter((c) => c.anti_dilution !== "none");
  const [classId, setClassId] = useState("");
  const [price, setPrice] = useState("");
  const [shares, setShares] = useState("");
  const [result, setResult] = useState<AntiDilutionPreview | null>(null);
  const [error, setError] = useState("");

  if (protectedClasses.length === 0) return null;

  return (
    <div className="card">
      <h3>Down-round calculator (anti-dilution)</h3>
      {error && <p className="error">{error}</p>}
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div>
          <label>Protected class</label>
          <select value={classId} onChange={(e) => setClassId(e.target.value)}>
            <option value="">—</option>
            {protectedClasses.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.anti_dilution})
              </option>
            ))}
          </select>
        </div>
        <div>
          <label>New round price (₹)</label>
          <input value={price} onChange={(e) => setPrice(e.target.value)} />
        </div>
        <div>
          <label>New shares issued</label>
          <input value={shares} onChange={(e) => setShares(e.target.value)} />
        </div>
        <button
          style={{ flex: "0 0 auto" }}
          disabled={!classId || !price || !shares}
          onClick={async () => {
            setError("");
            try {
              setResult(await api.antiDilution(entityId, classId, price, shares));
            } catch (e) {
              setError((e as Error).message);
            }
          }}
        >
          Compute
        </button>
      </div>
      {result && (
        <>
          <p className="muted">
            Conversion price ₹{result.orig_issue_price} → <strong>₹{result.adjusted_price}</strong> ·
            conversion ratio <strong>{result.conversion_ratio} : 1</strong> ({result.method})
          </p>
          <table>
            <thead>
              <tr><th>Holder</th><th>Held</th><th>Additional shares on conversion</th></tr>
            </thead>
            <tbody>
              {result.holders.map((h) => (
                <tr key={h.stakeholder_id}>
                  <td>{h.stakeholder_name}</td>
                  <td>{h.held.toLocaleString()}</td>
                  <td>{h.additional_shares.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { api, type FullyDiluted as FullyDilutedT } from "../api";

/** The as-if-converted view: issued + options + pool + SAFEs/notes. */
export default function FullyDilutedView({
  entityId,
  refreshKey,
}: {
  entityId: string;
  refreshKey?: number;
}) {
  const [fd, setFd] = useState<FullyDilutedT | null>(null);
  const [price, setPrice] = useState("");
  const [error, setError] = useState("");

  async function load(assumed?: string) {
    setError("");
    try {
      setFd(await api.fullyDiluted(entityId, assumed));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  useEffect(() => {
    load(price || undefined);
  }, [entityId, refreshKey]);

  return (
    <>
      {error && <p className="error">{error}</p>}
      <div className="row" style={{ alignItems: "flex-end" }}>
        <div>
          <label>Assumed conversion price (₹/share; blank = current FMV)</label>
          <input value={price} onChange={(e) => setPrice(e.target.value)} placeholder="e.g. 100" />
        </div>
        <button style={{ flex: "0 0 auto" }} onClick={() => load(price || undefined)}>
          Recompute
        </button>
      </div>
      {fd && (
        <>
          <p className="muted">
            Fully diluted: <strong>{fd.fully_diluted_shares.toLocaleString()}</strong> ·
            Issued {fd.issued_shares.toLocaleString()} · Options {fd.option_shares.toLocaleString()} ·
            Pool {fd.pool_unallocated.toLocaleString()} · Converts {fd.convertible_shares.toLocaleString()}
            {fd.assumed_price && <> · at ₹{fd.assumed_price}/share</>}
          </p>
          {fd.excluded_instruments.length > 0 && (
            <p className="error">
              Not priceable (set an assumed price or add a valuation):{" "}
              {fd.excluded_instruments.join(", ")}
            </p>
          )}
          <table>
            <thead>
              <tr>
                <th>Holder</th>
                <th>Type</th>
                <th>Issued</th>
                <th>Options</th>
                <th>Converts</th>
                <th>Total</th>
                <th>FD %</th>
              </tr>
            </thead>
            <tbody>
              {fd.rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.name}</td>
                  <td>{r.type}</td>
                  <td>{r.issued.toLocaleString()}</td>
                  <td>{r.options.toLocaleString()}</td>
                  <td>{r.converts.toLocaleString()}</td>
                  <td>{r.total.toLocaleString()}</td>
                  <td>{r.pct}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}

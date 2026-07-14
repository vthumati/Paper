import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, type PortalDashboard } from "../api";
import Stat from "../components/Stat";

export default function Portal() {
  const nav = useNavigate();
  const [d, setD] = useState<PortalDashboard | null>(null);
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);

  const load = () =>
    api
      .portal()
      .then(setD)
      .catch((e) => setError(e.message))
      .finally(() => setLoaded(true));
  useEffect(() => {
    load();
  }, []);

  const act = (fn: () => Promise<unknown>) => async () => {
    setError("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  const empty =
    loaded && d && d.companies.length === 0 && d.funds.length === 0 && d.equity_grants.length === 0;

  return (
    <div>
      <p className="muted">
        <a href="#" onClick={(e) => { e.preventDefault(); nav("/"); }}>
          ← Organisations
        </a>
      </p>
      <h1>Investor portal</h1>
      {error && <p className="error">{error}</p>}

      {d && (d.companies.length > 0 || d.funds.length > 0 || d.equity_grants.length > 0) && (
        <div className="card">
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Companies" value={d.summary.companies} />
            <Stat label="Funds (as LP)" value={d.summary.funds} />
            <Stat label="Invested (₹)" value={d.summary.total_invested} />
            <Stat label="Portfolio value (₹)" value={d.summary.portfolio_value} big />
            {d.summary.moic && <Stat label="MOIC" value={`${d.summary.moic}×`} big />}
            <Stat label="Committed to funds (₹)" value={d.summary.total_committed} />
            {d.equity_grants.length > 0 && (
              <>
                <Stat label="Options vested" value={d.summary.options_vested.toLocaleString()} />
                <Stat label="Exercisable" value={d.summary.options_exercisable.toLocaleString()} />
              </>
            )}
          </div>
        </div>
      )}

      {d && d.equity_grants.length > 0 && (
        <div className="card">
          <h2>Your equity (ESOP)</h2>
          <table>
            <thead>
              <tr>
                <th>Company</th>
                <th>Granted</th>
                <th>Vested</th>
                <th>Exercised</th>
                <th>Exercisable</th>
                <th>Strike</th>
                <th>FMV</th>
                <th>Unrealised gain</th>
              </tr>
            </thead>
            <tbody>
              {d.equity_grants.map((g, i) => (
                <tr key={i}>
                  <td>{g.entity_name}</td>
                  <td>{g.granted.toLocaleString()}</td>
                  <td>{g.vested.toLocaleString()}</td>
                  <td>{g.exercised.toLocaleString()}</td>
                  <td>{g.exercisable.toLocaleString()}</td>
                  <td>₹{g.exercise_price}</td>
                  <td>{g.current_fmv ? `₹${g.current_fmv}` : "—"}</td>
                  <td>{g.unrealized_gain ? `₹${g.unrealized_gain}` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {empty && (
        <div className="card">
          <p className="muted">
            You don't have investor access yet. When a company or fund invites your email, your
            holdings, capital accounts, documents and updates appear here.
          </p>
        </div>
      )}

      {d?.companies.map((c) => (
        <div className="card" key={c.entity_id}>
          <h2>
            {c.entity_name} <span className="badge">{c.entity_type}</span>
            {Number(c.current_value) > 0 && (
              <span className="muted" style={{ fontSize: 14, marginLeft: 8 }}>
                position value ₹{c.current_value} (at latest FMV)
              </span>
            )}
          </h2>

          {c.consents.some((x) => x.status === "pending") && (
            <>
              <h3>Your consent is requested</h3>
              {c.consents.filter((x) => x.status === "pending").map((x) => (
                <div className="list-item" key={x.id}>
                  <strong>{x.title}</strong> <span className="badge">{x.type}</span>{" "}
                  <button style={{ marginLeft: 8 }} onClick={act(() => api.decideConsent(x.id, true))}>
                    Approve
                  </button>{" "}
                  <button className="secondary" onClick={act(() => api.decideConsent(x.id, false))}>
                    Reject
                  </button>
                </div>
              ))}
            </>
          )}

          <h3>Your holdings</h3>
          {c.holdings.length === 0 ? (
            <p className="muted">No holdings on record.</p>
          ) : (
            <table>
              <thead><tr><th>Security</th><th>Quantity</th><th>Invested (₹)</th><th>Ownership %</th><th></th></tr></thead>
              <tbody>
                {c.holdings.map((h, i) => (
                  <tr key={i}>
                    <td>{h.security_class}</td>
                    <td>{h.quantity.toLocaleString()}</td>
                    <td>{h.amount_invested}</td>
                    <td>{h.ownership_pct}%</td>
                    <td>
                      <button
                        className="secondary"
                        onClick={act(async () => {
                          const qty = window.prompt(`Sell how many ${h.security_class} shares? (you hold ${h.quantity.toLocaleString()})`);
                          if (!qty) return;
                          const price = window.prompt("Asking price per share (₹):");
                          if (!price) return;
                          await api.requestSale({
                            entity_id: c.entity_id,
                            security_class_id: h.security_class_id,
                            quantity: Number(qty),
                            price_per_unit: price,
                          });
                        })}
                      >
                        Request sale
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {c.sale_requests.length > 0 && (
            <p className="muted">
              Sale requests:{" "}
              {c.sale_requests.map((r) => `${r.quantity.toLocaleString()} @ ₹${r.price_per_unit} (${r.status})`).join(" · ")}
              {" — the company decides under its right of first refusal."}
            </p>
          )}

          {c.instruments.length > 0 && (
            <>
              <h3>Your SAFEs &amp; convertible notes</h3>
              <table>
                <thead><tr><th>Type</th><th>Principal (₹)</th><th>Cap</th><th>Discount</th><th>Issued</th><th>Status</th></tr></thead>
                <tbody>
                  {c.instruments.map((x) => (
                    <tr key={x.id}>
                      <td>{x.instrument_type === "safe" ? "SAFE" : "Note"}</td>
                      <td>{x.principal}</td>
                      <td>{x.valuation_cap ? `₹${x.valuation_cap}` : "—"}</td>
                      <td>{Number(x.discount_pct) > 0 ? `${(Number(x.discount_pct) * 100).toFixed(0)}%` : "—"}</td>
                      <td>{x.issue_date}</td>
                      <td>
                        <span className={`badge ${x.status === "converted" ? "complete" : ""}`}>
                          {x.status}{x.converted_shares ? ` (${x.converted_shares.toLocaleString()} shares)` : ""}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}

          {c.documents.length > 0 && (
            <>
              <h3>Documents shared with you</h3>
              <ul className="muted">
                {c.documents.map((doc) => (
                  <li key={doc.id}>{doc.title} <span className="badge">{doc.data_room}</span></li>
                ))}
              </ul>
            </>
          )}

          <h3>Updates</h3>
          {c.updates.length === 0 ? (
            <p className="muted">No updates yet.</p>
          ) : (
            c.updates.map((u) => (
              <div key={u.id} style={{ borderTop: "1px solid var(--border)", padding: "8px 0" }}>
                <strong>{u.title}</strong>{" "}
                <span className="muted">{new Date(u.created_at).toLocaleDateString()}</span>
                <div className="muted">{u.body}</div>
              </div>
            ))
          )}
        </div>
      ))}

      {d?.funds.map((f) => (
        <div className="card" key={f.fund_id}>
          <h2>{f.fund_name} <span className="badge">AIF Cat {f.sebi_category}</span></h2>
          {f.performance && f.performance.paid_in !== "0.00" && (
            <p className="muted">
              Fund performance: DPI {f.performance.dpi ?? "—"} · <strong>TVPI {f.performance.tvpi ?? "—"}</strong> · XIRR{" "}
              {f.performance.xirr_pct !== null ? `${f.performance.xirr_pct}%` : "—"} · NAV ₹{f.performance.nav}
            </p>
          )}
          {f.statements.length > 0 && (
            <>
              <h3>Your statements</h3>
              <ul className="muted">
                {f.statements.map((s) => (
                  <li key={s.id}>{s.title}</li>
                ))}
              </ul>
            </>
          )}
          <h3>Your capital account</h3>
          {f.account ? (
            <table>
              <thead><tr><th>Committed</th><th>Drawn</th><th>Remaining</th><th>Distributed</th></tr></thead>
              <tbody>
                <tr>
                  <td>₹{f.account.committed}</td>
                  <td>₹{f.account.drawn}</td>
                  <td>₹{f.account.remaining}</td>
                  <td>₹{f.account.distributed}</td>
                </tr>
              </tbody>
            </table>
          ) : (
            <p className="muted">No capital account on record.</p>
          )}
          {f.updates.length > 0 && (
            <>
              <h3>Updates</h3>
              {f.updates.map((u) => (
                <div key={u.id} style={{ borderTop: "1px solid var(--border)", padding: "8px 0" }}>
                  <strong>{u.title}</strong>{" "}
                  <span className="muted">{new Date(u.created_at).toLocaleDateString()}</span>
                  <div className="muted">{u.body}</div>
                </div>
              ))}
            </>
          )}
        </div>
      ))}
    </div>
  );
}


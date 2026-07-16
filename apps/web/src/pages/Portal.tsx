import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { uiPrompt } from "../components/Prompt";
import { useNavigate } from "react-router-dom";
import { api, type PortalDashboard, type ValueHistory } from "../api";
import LineChart from "../components/LineChart";
import SecChip from "../components/SecChip";
import Stat from "../components/Stat";
import GrantDetail from "../features/GrantDetail";
import { fmtMoney } from "../lib/format";
import { useGuard } from "../hooks";
import Skeleton from "../components/Skeleton";

const RANGES = [
  { key: "3M", months: 3 },
  { key: "6M", months: 6 },
  { key: "1Y", months: 12 },
  { key: "All", months: 0 },
] as const;

export default function Portal() {
  const nav = useNavigate();
  const [d, setD] = useState<PortalDashboard | null>(null);
  const [hist, setHist] = useState<ValueHistory | null>(null);
  const [range, setRange] = useState<string>("All");
  const [openGrant, setOpenGrant] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);

  const load = () => {
    api.portalValueHistory().then(setHist).catch(() => {});
    return api
      .portal()
      .then(setD)
      .catch((e) => setError(e.message))
      .finally(() => setLoaded(true));
  };
  useEffect(() => {
    load();
  }, []);

  const rangePoints = (() => {
    if (!hist || hist.series.length === 0) return [];
    const months = RANGES.find((r) => r.key === range)?.months ?? 0;
    let pts = hist.series;
    if (months > 0) {
      const cutoff = new Date();
      cutoff.setMonth(cutoff.getMonth() - months);
      const iso = cutoff.toISOString().slice(0, 10);
      pts = pts.filter((p) => p.date >= iso);
    }
    return pts.map((p) => ({ x: p.date, y: Number(p.value) }));
  })();

  const { error, setError, guard } = useGuard(load);

  const empty =
    loaded && d && d.companies.length === 0 && d.funds.length === 0 &&
    d.spvs.length === 0 && d.equity_grants.length === 0;

  return (
    <div>
      <p className="muted">
        <a href="#" onClick={(e) => { e.preventDefault(); nav("/"); }}>
          ← Organisations
        </a>
      </p>
      <h1>Investor portal</h1>
      {error && <p className="error">{error}</p>}

      {!loaded && (
        <div className="card">
          <Skeleton lines={5} height={18} />
        </div>
      )}

      {hist && hist.holdings > 0 && (
        <div className="card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: 8 }}>
            <div>
              <div className="muted" style={{ fontSize: 12 }}>Equity holdings — marked value</div>
              <div style={{ fontSize: 30, fontWeight: 700, color: "var(--heading)" }}>
                {fmtMoney(hist.current_value)}
              </div>
            </div>
            <div className="tabs subtabs" style={{ borderBottom: "none" }}>
              {RANGES.map((r) => (
                <button key={r.key} className={range === r.key ? "active" : ""} onClick={() => setRange(r.key)}>
                  {r.key}
                </button>
              ))}
            </div>
          </div>
          <LineChart
            series={[{ label: "Marked value", color: "#2f6b52", points: rangePoints }]}
            height={180}
          />
          <p className="muted" style={{ marginTop: 4, fontSize: 12 }}>
            Company equity marked at each valuation date (held at cost before the first valuation).
            Fund and SPV positions are shown separately below.
          </p>
        </div>
      )}

      {d && (d.companies.length > 0 || d.funds.length > 0 || d.spvs.length > 0 || d.equity_grants.length > 0) && (
        <div className="card">
          <div className="row" style={{ gap: 10 }}>
            <Stat label="Companies" value={d.summary.companies} hint="Companies where you hold equity or instruments." />
            <Stat label="Funds (as LP)" value={d.summary.funds} hint="Funds where you are a limited partner." />
            {d.spvs.length > 0 && <Stat label="SPV deals" value={d.summary.spvs} hint="Syndicate/SPV deals you're invited to or invested in." />}
            <Stat label="Invested (₹)" value={d.summary.total_invested} hint="Total you have paid in across all holdings." />
            <Stat label="Portfolio value (₹)" value={d.summary.portfolio_value} big hint="Current value: company holdings at latest FMV, plus fund/SPV positions at cost." />
            {d.summary.moic && <Stat label="MOIC" value={`${d.summary.moic}×`} big hint="Multiple on invested capital = portfolio value ÷ invested." />}
            <Stat label="Committed to funds (₹)" value={d.summary.total_committed} hint="Capital you've committed to funds/SPVs." />
            {d.equity_grants.length > 0 && (
              <>
                <Stat label="Options vested" value={d.summary.options_vested.toLocaleString()} hint="Your options vested to date." />
                <Stat label="Exercisable" value={d.summary.options_exercisable.toLocaleString()} hint="Vested options you can exercise now." />
              </>
            )}
          </div>
        </div>
      )}

      {d && d.equity_grants.length > 0 && (() => {
        const granted = d.equity_grants.reduce((s, g) => s + g.granted, 0);
        const vested = d.equity_grants.reduce((s, g) => s + g.vested, 0);
        const pct = granted > 0 ? (vested / granted) * 100 : 0;
        const fullVest = d.equity_grants.map((g) => g.full_vest_date).sort().slice(-1)[0];
        const sum = (f: (g: PortalDashboard["equity_grants"][number]) => string | null) =>
          d.equity_grants.reduce((s, g) => s + Number(f(g) ?? 0), 0);
        const todayValue = sum((g) => g.today_value);
        const potential = sum((g) => g.max_potential_value);
        const nextVest = d.equity_grants
          .flatMap((g) => g.next_vests.map((ev) => ev.date))
          .sort()[0];
        const upcoming = d.equity_grants
          .flatMap((g) => g.next_vests.map((ev) => ({ ...ev, entity: g.entity_name })))
          .sort((a, b) => a.date.localeCompare(b.date))
          .slice(0, 5);
        return (
        <div className="card">
          <h2>Your equity (ESOP)</h2>
          {/* Ledgy-style hero: today's value vs total potential, vested bar */}
          <div style={{ display: "flex", justifyContent: "space-between", flexWrap: "wrap", gap: 8 }}>
            <div>
              <div className="muted" style={{ fontSize: 12 }}>Today's value (vested)</div>
              <div style={{ fontSize: 30, fontWeight: 700, color: "var(--heading)" }}>
                {fmtMoney(todayValue)}
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div className="muted" style={{ fontSize: 12 }}>Max potential value</div>
              <div style={{ fontSize: 20, fontWeight: 700 }}>{fmtMoney(potential)}</div>
            </div>
          </div>
          <div style={{ margin: "10px 0 4px" }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginBottom: 4 }}>
              <span className="badge complete">{pct.toFixed(0)}% vested</span>
              <span className="muted">{(100 - pct).toFixed(0)}% unvested</span>
            </div>
            <div className="progress-track">
              <div className="progress-fill" style={{ width: `${Math.min(100, pct)}%` }} />
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 12, marginTop: 6 }}>
              <span className="muted">Next vesting date: <strong>{nextVest ?? "—"}</strong></span>
              <span className="muted">Fully vested: <strong>{fullVest ?? "—"}</strong></span>
            </div>
          </div>
          {openGrant && (
            <GrantDetail grantId={openGrant} onClose={() => setOpenGrant(null)} />
          )}
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
                <th></th>
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
                  <td style={{ whiteSpace: "nowrap" }}>
                    <button className="secondary" onClick={() => setOpenGrant(g.grant_id)}>
                      View
                    </button>{" "}
                    {g.exercise_requests.some((r) => r.status === "open") ? (
                      <span className="badge">request pending</span>
                    ) : (
                      g.exercisable > 0 && (
                        <button
                          className="secondary"
                          onClick={guard(async () => {
                            const qty = await uiPrompt(`Exercise how many options? (${g.exercisable.toLocaleString()} exercisable)`);
                            if (!qty) return;
                            await api.requestExercise({ grant_id: g.grant_id, quantity: Number(qty) });
                          })}
                        >
                          Request exercise
                        </button>
                      )
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {upcoming.length > 0 && (
            <>
              <h3>Upcoming vest events</h3>
              {upcoming.map((ev, i) => (
                <div className="timeline-row" key={i}>
                  <span className="tl-date">{ev.date}</span>
                  <span>
                    {ev.quantity.toLocaleString()} options will vest
                    {ev.entity ? ` · ${ev.entity}` : ""}
                  </span>
                </div>
              ))}
            </>
          )}
        </div>
        );
      })()}

      {d && d.liquidity_events.length > 0 && (
        <div className="card">
          <h2>Liquidity windows</h2>
          <p className="muted">Companies buying back shares — tender yours before the window closes.</p>
          {d.liquidity_events.map((ev) => (
            <div key={ev.id} style={{ borderTop: "1px solid var(--border)", padding: "10px 0" }}>
              <strong>{ev.name}</strong> <span className="muted">· {ev.entity_name}</span>{" "}
              <span className="badge active">{ev.kind}</span>
              <div className="muted" style={{ margin: "4px 0" }}>
                ₹{ev.price_per_share}/share · closes {ev.closes_on}
                {ev.my_tendered > 0 && ` · you've tendered ${ev.my_tendered.toLocaleString()}`}
              </div>
              {ev.holdings.map((hld) => (
                <div key={hld.security_class_id} style={{ marginTop: 4 }}>
                  <SecChip name={hld.security_class} kind={hld.kind} />{" "}
                  <span className="muted">{hld.quantity.toLocaleString()} held</span>{" "}
                  <button
                    className="secondary"
                    onClick={guard(async () => {
                      const qty = await uiPrompt(
                        `Tender how many ${hld.security_class} shares at ₹${ev.price_per_share}? (you hold ${hld.quantity.toLocaleString()})`
                      );
                      if (!qty) return;
                      await api.tenderShares({
                        event_id: ev.id,
                        security_class_id: hld.security_class_id,
                        quantity: Number(qty),
                      });
                    })}
                  >
                    Tender
                  </button>
                </div>
              ))}
            </div>
          ))}
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
                  <button style={{ marginLeft: 8 }} onClick={guard(() => api.decideConsent(x.id, true))}>
                    Approve
                  </button>{" "}
                  <button className="secondary" onClick={guard(() => api.decideConsent(x.id, false))}>
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
                    <td><SecChip name={h.security_class} kind={h.kind} /></td>
                    <td>{h.quantity.toLocaleString()}</td>
                    <td>{h.amount_invested}</td>
                    <td>{h.ownership_pct}%</td>
                    <td>
                      <button
                        className="secondary"
                        onClick={guard(async () => {
                          const qty = await uiPrompt(`Sell how many ${h.security_class} shares? (you hold ${h.quantity.toLocaleString()})`);
                          if (!qty) return;
                          const price = await uiPrompt("Asking price per share (₹):");
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
            <EmptyState icon="📣" title="No updates yet" hint="Investor updates the company publishes will appear here." />
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

      {d && d.spvs.length > 0 && (
        <div className="card">
          <h2>Your SPV deals</h2>
          <table>
            <thead>
              <tr>
                <th>SPV</th>
                <th>Target</th>
                <th>Sponsor</th>
                <th>Carry</th>
                <th>Min ticket</th>
                <th>Status</th>
                <th>Commitment</th>
                <th>Contributed</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {d.spvs.map((s) => (
                <tr key={s.co_investor_id}>
                  <td>{s.spv_name ?? "—"}</td>
                  <td>{s.target_company}</td>
                  <td>{s.sponsor}</td>
                  <td>{(Number(s.carry_pct) * 100).toFixed(1)}%</td>
                  <td>₹{s.min_ticket}</td>
                  <td>
                    <span className={`badge ${s.status === "funded" ? "complete" : ""}`}>
                      {s.status}
                    </span>
                  </td>
                  <td>₹{s.commitment}</td>
                  <td>₹{s.contributed}</td>
                  <td>
                    {s.status !== "funded" && (
                      <button
                        className="secondary"
                        onClick={guard(async () => {
                          const amt = await uiPrompt(
                            `Commit how much (₹)? Minimum ticket ₹${s.min_ticket}`,
                            s.commitment !== "0.00" ? s.commitment : ""
                          );
                          if (!amt) return;
                          await api.commitToSPV({ co_investor_id: s.co_investor_id, amount: amt });
                        })}
                      >
                        {s.status === "invited" ? "Commit" : "Revise commitment"}
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {d.spvs.some((s) => s.documents.length > 0) && (
            <>
              <h3>Your deal documents</h3>
              <ul className="muted">
                {d.spvs.flatMap((s) =>
                  s.documents.map((doc) => (
                    <li key={doc.id}>
                      {doc.title} <span className="badge">{doc.status}</span>{" "}
                      <a
                        href="#"
                        onClick={(e) => {
                          e.preventDefault();
                          api.downloadPortalDocPdf(doc.id, doc.title).catch((err) => setError(err.message));
                        }}
                      >
                        PDF
                      </a>
                    </li>
                  ))
                )}
              </ul>
            </>
          )}
          {d.spvs.some((s) => s.updates.length > 0) && (
            <>
              <h3>Deal updates</h3>
              {d.spvs.flatMap((s) =>
                s.updates.map((u) => (
                  <div key={u.id} style={{ borderTop: "1px solid var(--border)", padding: "8px 0" }}>
                    <strong>{u.title}</strong>{" "}
                    <span className="muted">{new Date(u.created_at).toLocaleDateString()}</span>
                    <div className="muted">{u.body}</div>
                  </div>
                ))
              )}
            </>
          )}
        </div>
      )}

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
                  <li key={s.id}>
                    {s.title}{" "}
                    <a
                      href="#"
                      onClick={(e) => {
                        e.preventDefault();
                        api.downloadPortalDocPdf(s.id, s.title).catch((err) => setError(err.message));
                      }}
                    >
                      PDF
                    </a>
                  </li>
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
          {f.look_through && f.look_through.holdings.length > 0 && (
            <>
              <h3>
                Look-through to underlying companies{" "}
                <span className="muted" style={{ fontSize: 13 }}>
                  (your {f.look_through.share_pct}% share of the fund)
                </span>
              </h3>
              <table>
                <thead>
                  <tr>
                    <th>Company</th>
                    <th>Fund value</th>
                    <th>Your cost</th>
                    <th>Your value</th>
                    <th>MOIC</th>
                  </tr>
                </thead>
                <tbody>
                  {f.look_through.holdings.map((hld, i) => (
                    <tr key={i}>
                      <td>{hld.company_name} <span className="muted">{hld.instrument}</span></td>
                      <td className="muted">₹{hld.fund_value}</td>
                      <td>₹{hld.look_through_cost}</td>
                      <td>₹{hld.look_through_value}</td>
                      <td>{hld.moic ? `${hld.moic}×` : "—"}</td>
                    </tr>
                  ))}
                  <tr style={{ fontWeight: 700, borderTop: "2px solid var(--border)" }}>
                    <td>Your total exposure</td>
                    <td></td>
                    <td>₹{f.look_through.totals.look_through_cost}</td>
                    <td>₹{f.look_through.totals.look_through_value}</td>
                    <td></td>
                  </tr>
                </tbody>
              </table>
              <p className="muted" style={{ fontSize: 12 }}>
                Your pro-rata slice of the fund's holdings, at the fund's reported marks.
              </p>
            </>
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


import { useEffect, useState } from "react";
import {
  api,
  type CompanyNote,
  type InvestmentRounds,
  type PortfolioInvestment,
  type PortfolioMonitoring,
  type PortfolioSignals,
  type SOIHolding,
} from "../api";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";
import Avatar from "../components/Avatar";
import ComboChart from "../components/ComboChart";
import Stat from "../components/Stat";

const todayIso = () => new Date().toISOString().slice(0, 10);

const SEVERITY_ICON: Record<string, string> = { high: "🔴", warn: "🟠", info: "🔵", positive: "🟢" };

/** On-screen company tear sheet (Visible-style): investment info tiles, the
 * revenue & growth combo chart, latest KPIs and active signals — the document
 * generator stays for the exportable version. */
export default function TearSheet({
  fundId,
  inv,
  soiRow,
  onClose,
  onChanged,
}: {
  fundId: string;
  inv: PortfolioInvestment;
  soiRow: SOIHolding | null;
  onClose: () => void;
  onChanged?: () => void;
}) {
  const [mon, setMon] = useState<PortfolioMonitoring | null>(null);
  const [signals, setSignals] = useState<PortfolioSignals | null>(null);
  const [rounds, setRounds] = useState<InvestmentRounds | null>(null);
  const [notes, setNotes] = useState<CompanyNote[]>([]);
  const [roundOpen, setRoundOpen] = useState(false);
  const [rAmount, setRAmount] = useState("");
  const [rLabel, setRLabel] = useState("");
  const [rDate, setRDate] = useState(todayIso());
  const [noteBody, setNoteBody] = useState("");
  const { error, guard } = useGuard();

  useEffect(() => {
    api.portfolioMonitoring(fundId).then(setMon);
    api.portfolioSignals(fundId).then(setSignals);
    api.listInvestmentRounds(fundId, inv.id).then(setRounds);
    api.listCompanyNotes(fundId, inv.id).then(setNotes);
  }, [fundId, inv.id]);

  const company = mon?.companies.find((c) => c.investment_id === inv.id) ?? null;
  const companySignals = signals?.companies.find((c) => c.investment_id === inv.id)?.signals ?? [];

  const series = company?.revenue_series ?? [];
  const categories = series.map((p) => p.x.slice(0, 7));
  const bars = series.map((p) => p.y as number | null);
  const growth = series.map((p, i) =>
    i === 0 || !series[i - 1].y ? null : ((p.y - series[i - 1].y) / series[i - 1].y) * 100
  );

  const latest = company?.latest ?? null;

  return (
    <div className="card" style={{ borderLeft: "3px solid var(--navy)" }}>
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <Avatar name={inv.company_name} /> {inv.company_name}
        {inv.sector && <span className="badge">{inv.sector}</span>}
        <span className="badge">{inv.instrument}</span>
        {inv.invested_on && <span className="muted" style={{ fontSize: 12 }}>since {inv.invested_on}</span>}
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          <button
            className="secondary"
            onClick={guard(
              () => api.tearSheet(fundId, inv.id),
              "Tear-sheet document generated — see the Documents tab"
            )}
          >
            Generate document
          </button>
          <button className="secondary" onClick={onClose}>Close</button>
        </span>
      </h3>
      {error && <p className="error">{error}</p>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: 10 }}>
        <Stat label="Amount invested" value={fmtMoney(inv.amount)} />
        <Stat
          label="Fair value"
          value={inv.current_value ? fmtMoney(inv.current_value) : fmtMoney(inv.amount)}
          hint={inv.current_value ? `Marked on ${inv.marked_on}` : "Held at cost — no mark yet"}
        />
        {soiRow?.moic && <Stat label="MOIC" value={`${soiRow.moic}×`} />}
        <Stat label="Ownership" value={`${inv.ownership_pct}%`} />
        {soiRow && <Stat label="% of NAV" value={`${soiRow.pct_of_nav}%`} />}
        {company?.runway_months !== null && company?.runway_months !== undefined && (
          <Stat label="Runway" value={`${company.runway_months} mo`} alert={company.low_runway} />
        )}
      </div>

      {series.length > 1 && (
        <div style={{ marginTop: 12 }}>
          <ComboChart
            categories={categories}
            bars={bars}
            line={growth}
            barLabel="Revenue"
            lineLabel="Growth %"
            height={190}
          />
        </div>
      )}

      {latest && (
        <p className="muted" style={{ marginTop: 10 }}>
          Latest period <strong>{latest.period_label}</strong> (as of {latest.as_of}): revenue{" "}
          {latest.revenue ? fmtMoney(latest.revenue) : "—"} · cash {latest.cash ? fmtMoney(latest.cash) : "—"} ·
          burn {latest.monthly_burn ? fmtMoney(latest.monthly_burn) : "—"} · headcount {latest.headcount ?? "—"}
          {latest.custom &&
            Object.entries(latest.custom).map(([k, v]) => (
              <span key={k}> · {k.replace(/_/g, " ")} {v}</span>
            ))}
        </p>
      )}
      {!company && mon && (
        <p className="muted" style={{ marginTop: 10 }}>No KPI periods reported yet — request KPIs from Monitoring.</p>
      )}

      <div style={{ marginTop: 8 }}>
        {companySignals.length === 0 ? (
          <p className="muted">🟢 No active signals — nothing needs attention.</p>
        ) : (
          companySignals.map((s, i) => (
            <div key={i} style={{ padding: "3px 0" }}>
              {SEVERITY_ICON[s.severity] ?? "•"}{" "}
              <span className="badge">{s.kind.replace(/_/g, " ")}</span>{" "}
              <span className="muted">{s.message}</span>
            </div>
          ))
        )}
      </div>

      {rounds && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <strong style={{ color: "var(--heading)" }}>Investment history</strong>
            <span className="muted" style={{ fontSize: 12 }}>total cost {fmtMoney(rounds.total_cost)}</span>
            <button className="secondary" style={{ marginLeft: "auto" }} onClick={() => setRoundOpen((v) => !v)}>
              {roundOpen ? "Close" : "Add follow-on"}
            </button>
          </div>
          <ul className="muted" style={{ margin: "6px 0 0", lineHeight: 1.7 }}>
            <li>
              Initial · {rounds.initial.instrument} · <strong>{fmtMoney(rounds.initial.amount)}</strong>
              {rounds.initial.invested_on && <> · {rounds.initial.invested_on}</>}
            </li>
            {rounds.rounds.map((r) => (
              <li key={r.id}>
                {r.round_label || "Follow-on"} · {r.instrument} · <strong>{fmtMoney(r.amount)}</strong>
                {r.invested_on && <> · {r.invested_on}</>}
                {r.note && <> — {r.note}</>}
              </li>
            ))}
          </ul>
          {roundOpen && (
            <div className="row" style={{ alignItems: "flex-end", marginTop: 8 }}>
              <div><label>Amount (₹)</label><input value={rAmount} onChange={(e) => setRAmount(e.target.value)} /></div>
              <div><label>Round</label><input placeholder="Series A" value={rLabel} onChange={(e) => setRLabel(e.target.value)} /></div>
              <div><label>Date</label><input type="date" value={rDate} onChange={(e) => setRDate(e.target.value)} /></div>
              <button
                style={{ flex: "0 0 auto" }}
                disabled={!rAmount || isNaN(Number(rAmount)) || Number(rAmount) <= 0}
                onClick={guard(async () => {
                  setRounds(await api.addInvestmentRound(fundId, inv.id, {
                    amount: rAmount, round_label: rLabel || null, invested_on: rDate || null,
                  }));
                  setRAmount(""); setRLabel("");
                  onChanged?.(); // parent refreshes portfolio totals
                }, "Follow-on recorded — total cost updated")}
              >
                Record follow-on
              </button>
            </div>
          )}
        </div>
      )}

      <div style={{ marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--border)" }}>
        <strong style={{ color: "var(--heading)" }}>Team notes</strong>{" "}
        <span className="muted" style={{ fontSize: 12 }}>internal only — never shown to LPs or the company</span>
        {notes.map((n) => (
          <div key={n.id} style={{ padding: "4px 0", display: "flex", gap: 8, alignItems: "baseline" }}>
            <span style={{ flex: 1 }}>
              {n.body}{" "}
              <span className="muted" style={{ fontSize: 12 }}>
                — {n.author ?? "someone"} · {new Date(n.created_at).toLocaleDateString()}
              </span>
            </span>
            <button
              className="secondary"
              style={{ flex: "0 0 auto" }}
              onClick={guard(async () => {
                await api.deleteCompanyNote(fundId, inv.id, n.id);
                setNotes(await api.listCompanyNotes(fundId, inv.id));
              }, "Note removed")}
            >
              ×
            </button>
          </div>
        ))}
        <div style={{ display: "flex", gap: 8, marginTop: 6 }}>
          <input
            style={{ flex: 1 }}
            placeholder="Add a note for the team…"
            value={noteBody}
            onChange={(e) => setNoteBody(e.target.value)}
          />
          <button
            style={{ flex: "0 0 auto" }}
            disabled={!noteBody.trim()}
            onClick={guard(async () => {
              setNotes(await api.addCompanyNote(fundId, inv.id, noteBody));
              setNoteBody("");
            }, "Note added")}
          >
            Add note
          </button>
        </div>
      </div>
    </div>
  );
}

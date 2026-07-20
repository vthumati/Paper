import { useEffect, useState } from "react";
import { api, type FundFinancials as Financials } from "../api";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";

/** Fund financial statements (Carta "fund accounting", no GL export): a
 * since-inception statement of operations, cash flows, assets & liabilities and
 * a partners'-capital roll-forward — all derived from the existing ledgers and
 * portfolio marks, tying out so net assets == ending partners' capital. */
export default function FundFinancials({ fundId }: { fundId: string }) {
  const [fin, setFin] = useState<Financials | null>(null);
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const { error, guard } = useGuard(() => load());

  const load = () => api.fundFinancials(fundId).then(setFin);
  useEffect(() => {
    load();
  }, [fundId]);

  if (!fin) return null;
  const { operations: op, cash_flow: cf, balance_sheet: bs, capital_roll_forward: rf, disclosures: d } = fin;

  // signed money: server sends negatives as "-1234.00"; render "(₹1,234)"
  const money = (v: string) =>
    v.startsWith("-") ? `(${fmtMoney(v.slice(1))})` : fmtMoney(v);

  return (
    <div className="card">
      <h3 style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span>📄</span> Financial statements
        <span className={`badge ${fin.balances ? "complete" : "danger"}`}>
          {fin.balances ? "✓ balances" : "out of balance"}
        </span>
        <button className="secondary" style={{ marginLeft: "auto" }} onClick={() => setOpen((v) => !v)}>
          {open ? "Hide" : "View statements"}
        </button>
      </h3>
      <p className="muted" style={{ marginTop: 0 }}>
        Since inception, from the fund's ledgers. A management view — cash is derived (no bank ledger),
        realised gains aren't split from marks; not audited.
      </p>
      {error && <p className="error">{error}</p>}
      {note && <p className="muted">{note}</p>}

      {open && (
        <>
          <div className="row" style={{ alignItems: "flex-start" }}>
            <Statement title="Statement of operations" rows={[
              ["Realised gains", op.realized_gains],
              ["Unrealised appreciation", op.unrealized_appreciation],
              ["Total investment income", op.total_investment_income],
              ["Management fees", "-" + op.management_fees],
              ["Net increase from operations", op.net_increase_from_operations, true],
            ]} money={money} />

            <Statement title="Statement of cash flows" rows={[
              ["Capital contributions", cf.contributions],
              ["Investments made", cf.investments_made],
              ["Distributions to LPs", cf.distributions_to_lps],
              ["Carry paid to GP", cf.carry_paid],
              ["Management fees paid", cf.management_fees_paid],
              ["Ending cash", cf.ending_cash, true],
            ]} money={money} />
          </div>

          <div className="row" style={{ alignItems: "flex-start" }}>
            <Statement title="Assets & liabilities" rows={[
              ["Investments at fair value", bs.investments_at_fair_value],
              ["Cash", bs.cash],
              ["Total assets", bs.total_assets],
              ["Liabilities", bs.liabilities],
              ["Net assets", bs.net_assets, true],
            ]} money={money} />

            <Statement title="Partners' capital" rows={[
              ["Beginning", rf.beginning],
              ["Contributions", rf.contributions],
              ["Net increase from operations", rf.net_increase_from_operations],
              ["Distributions to LPs", rf.distributions_to_lps],
              ["Carry to GP", rf.carry_to_gp],
              ["Ending net assets", rf.ending_net_assets, true],
            ]} money={money} />
          </div>

          <p className="muted" style={{ marginTop: 4 }}>
            Committed {fmtMoney(d.committed)} · Uncalled {fmtMoney(d.uncalled)} · Invested at cost{" "}
            {fmtMoney(d.invested_at_cost)}
            {d.positions_at_cost > 0 && ` · ${d.positions_at_cost} position(s) held at cost`}
          </p>

          <button
            className="secondary"
            onClick={guard(async () => {
              await api.fundFinancialsReport(fundId);
              setNote("Financial statements generated (see Documents).");
            }, "Statements generated")}
          >
            Generate statement
          </button>
        </>
      )}
    </div>
  );
}

function Statement({
  title,
  rows,
  money,
}: {
  title: string;
  rows: [string, string, boolean?][];
  money: (v: string) => string;
}) {
  return (
    <div style={{ flex: 1, minWidth: 260 }}>
      <table>
        <thead>
          <tr><th colSpan={2}>{title}</th></tr>
        </thead>
        <tbody>
          {rows.map(([label, val, total], i) => (
            <tr key={i} style={total ? { fontWeight: 700, borderTop: "2px solid var(--border)" } : undefined}>
              <td style={total ? { color: "var(--heading)" } : { color: "var(--muted)" }}>{label}</td>
              <td style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{money(val)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

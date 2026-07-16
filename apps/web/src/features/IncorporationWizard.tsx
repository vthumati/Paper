import { useEffect, useState } from "react";
import { uiPrompt } from "../components/Prompt";
import { api, type Incorporation, type IncorporationFounder } from "../api";

const EMPTY_FOUNDER: IncorporationFounder = { name: "", email: "", din: "", shares: 0, is_director: true };

/** Atlas-style guided incorporation: one intake → filing pack → SRN → CIN,
 *  after which the company is live with shares, directors and a calendar. */
export default function IncorporationWizard({
  tenantId,
  onRegistered,
}: {
  tenantId: string;
  onRegistered?: () => void;
}) {
  const [incs, setIncs] = useState<Incorporation[]>([]);
  const [open, setOpen] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  const [name1, setName1] = useState("");
  const [name2, setName2] = useState("");
  const [state, setState] = useState("Karnataka");
  const [office, setOffice] = useState("");
  const [authCap, setAuthCap] = useState("1000000");
  const [paidCap, setPaidCap] = useState("100000");
  const [par, setPar] = useState("10");
  const [founders, setFounders] = useState<IncorporationFounder[]>([
    { ...EMPTY_FOUNDER },
    { ...EMPTY_FOUNDER },
  ]);

  const load = () => api.listIncorporations(tenantId).then(setIncs).catch((e) => setError(e.message));
  useEffect(() => {
    load();
  }, [tenantId]);

  const setFounder = (i: number, patch: Partial<IncorporationFounder>) =>
    setFounders(founders.map((f, j) => (j === i ? { ...f, ...patch } : f)));

  // live SPICe+ summary + Pulley-style pending-items notice
  const subscribed = founders.reduce((s, f) => s + (f.shares || 0), 0);
  const directorCount = founders.filter((f) => f.is_director && f.name).length;
  const missing: string[] = [];
  if (!name1) missing.push("proposed name");
  if (!office) missing.push("registered office");
  if (founders.some((f) => !f.name)) missing.push("founder names");
  if (founders.some((f) => !f.shares)) missing.push("founder shares");
  if (directorCount < 2) missing.push("at least 2 directors");
  if (Number(paidCap) > Number(authCap)) missing.push("paid-up capital exceeds authorised");
  if (subscribed * Number(par) > Number(authCap)) missing.push("subscription exceeds authorised capital");
  const spicePreview =
    `SPICe+ (INCORPORATION) — SUMMARY\n` +
    `Proposed company: ${name1 || "‹name›"}\n` +
    `${name2 ? `Alternate name: ${name2}\n` : ""}` +
    `State: ${state || "‹state›"}\nRegistered office: ${office || "‹address›"}\n\n` +
    `Authorised capital: INR ${Number(authCap || 0).toLocaleString()}\n` +
    `Paid-up capital:    INR ${Number(paidCap || 0).toLocaleString()}\n` +
    `Par value:          INR ${par}/share\n\n` +
    `SUBSCRIBERS (${subscribed.toLocaleString()} shares subscribed)\n` +
    founders
      .map((f) => ` - ${f.name || "‹founder›"} — ${(f.shares || 0).toLocaleString()} shares` +
        `${f.is_director ? " · director" : ""}${f.din ? ` · DIN ${f.din}` : ""}`)
      .join("\n") +
    `\n\nPack: SPICe+ summary · eMoA · eAoA · founder IP assignments`;

  const act = (fn: () => Promise<unknown>) => async () => {
    setError("");
    setNote("");
    try {
      await fn();
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  };

  return (
    <div className="card">
      <h2>
        Incorporate a company{" "}
        <button className="secondary" onClick={() => setOpen(!open)}>
          {open ? "Hide" : "Start"}
        </button>
      </h2>
      <p className="muted">
        One intake generates the SPICe+/eMoA/eAoA filing pack; when the CIN arrives, founder
        shares are allotted, directors registered and the compliance calendar created.
      </p>
      {error && <p className="error">{error}</p>}
      {note && <p>{note}</p>}

      {open && (
        <div className="row">
        <div style={{ flex: 1.2, minWidth: 340 }}>
          <div className="row">
            <div>
              <label>Proposed name (preferred)</label>
              <input value={name1} onChange={(e) => setName1(e.target.value)} placeholder="Zephyr Labs Private Limited" />
            </div>
            <div>
              <label>Alternate name (for RUN)</label>
              <input value={name2} onChange={(e) => setName2(e.target.value)} />
            </div>
            <div style={{ flex: "0 0 140px" }}>
              <label>State</label>
              <input value={state} onChange={(e) => setState(e.target.value)} />
            </div>
          </div>
          <label>Registered office address</label>
          <input value={office} onChange={(e) => setOffice(e.target.value)} />
          <div className="row">
            <div><label>Authorised capital (₹)</label><input value={authCap} onChange={(e) => setAuthCap(e.target.value)} /></div>
            <div><label>Paid-up capital (₹)</label><input value={paidCap} onChange={(e) => setPaidCap(e.target.value)} /></div>
            <div><label>Par value (₹/share)</label><input value={par} onChange={(e) => setPar(e.target.value)} /></div>
          </div>

          <h3>Founders (a Pvt Ltd needs at least 2 directors)</h3>
          {founders.map((f, i) => (
            <div className="row" key={i}>
              <input placeholder="Name" value={f.name} onChange={(e) => setFounder(i, { name: e.target.value })} />
              <input placeholder="Email (optional)" value={f.email ?? ""} onChange={(e) => setFounder(i, { email: e.target.value })} />
              <input placeholder="DIN (optional)" value={f.din ?? ""} onChange={(e) => setFounder(i, { din: e.target.value })} />
              <input placeholder="Shares" value={f.shares || ""} onChange={(e) => setFounder(i, { shares: Number(e.target.value) })} />
              <label style={{ flex: "0 0 auto", display: "flex", alignItems: "center", gap: 4 }}>
                <input type="checkbox" style={{ width: "auto" }} checked={f.is_director}
                  onChange={(e) => setFounder(i, { is_director: e.target.checked })} />
                director
              </label>
            </div>
          ))}
          {missing.length > 0 && (
            <p className="error" style={{ marginTop: 8 }}>
              {missing.length} item{missing.length > 1 ? "s" : ""} pending: {missing.join(", ")}
            </p>
          )}
          <button className="secondary" onClick={() => setFounders([...founders, { ...EMPTY_FOUNDER }])}>
            + Add founder
          </button>{" "}
          <button
            disabled={!name1 || !office || founders.some((f) => !f.name || !f.shares)}
            onClick={act(async () => {
              const inc = await api.createIncorporation(tenantId, {
                name_options: [name1, name2].filter(Boolean),
                state,
                registered_office: office,
                authorised_capital: authCap,
                paid_up_capital: paidCap,
                par_value: par,
                founders: founders.map((f) => ({ ...f, email: f.email || null, din: f.din || null })),
              });
              await api.prepareIncorporation(tenantId, inc.id);
              setOpen(false);
              setNote("Filing pack generated — see the new entity's Documents tab. File via your CS, then record the SRN and CIN below.");
            })}
          >
            Generate filing pack
          </button>
        </div>

        <div style={{ flex: 1, minWidth: 300 }}>
          <label>Live preview — SPICe+ summary</label>
          <div className="paper-sheet" style={{ fontSize: 13, padding: "22px 26px" }}>
            {spicePreview}
          </div>
        </div>
        </div>
      )}

      {incs.length > 0 && (
        <table style={{ marginTop: 10 }}>
          <thead>
            <tr><th>Company</th><th>Status</th><th>SRN</th><th>CIN</th><th></th></tr>
          </thead>
          <tbody>
            {incs.map((x) => (
              <tr key={x.id}>
                <td>{x.company_name ?? x.name_options[0]}</td>
                <td><span className={`badge ${x.status === "registered" ? "complete" : ""}`}>{x.status}</span></td>
                <td>{x.srn ?? "—"}</td>
                <td>{x.cin ?? "—"}</td>
                <td>
                  {x.status === "docs_generated" && (
                    <button
                      className="secondary"
                      onClick={act(async () => {
                        const srn = await uiPrompt("SRN from MCA filing:");
                        if (srn) await api.incorporationFiled(tenantId, x.id, srn);
                      })}
                    >
                      Mark filed
                    </button>
                  )}
                  {(x.status === "filed" || x.status === "docs_generated") && (
                    <button
                      className="secondary"
                      onClick={act(async () => {
                        const cin = await uiPrompt("CIN from the Certificate of Incorporation:");
                        if (!cin) return;
                        const date = await uiPrompt("Incorporation date (YYYY-MM-DD):");
                        if (!date) return;
                        const r = await api.incorporationRegistered(tenantId, x.id, {
                          cin, incorporation_date: date,
                        });
                        setNote(`Registered: ${r.shares_issued.toLocaleString()} shares allotted, ${r.directors_registered} directors, ${r.obligations_created} compliance obligations created.`);
                        onRegistered?.();
                      })}
                    >
                      Record CIN
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

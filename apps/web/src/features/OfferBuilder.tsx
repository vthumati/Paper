import { useEffect, useState } from "react";
import { api } from "../api";
import { useGuard } from "../hooks";
import { fmtMoney } from "../lib/format";

interface Pkg {
  salary: string;
  options: string;
  bonus: string;
}

const MULTIPLES = [1, 2, 5, 10];

/** Pulley-style offer experience: 1–3 selectable compensation packages with a
 * live preview and an illustrative equity-value projection at exit multiples;
 * generates the offer letter as a document. */
export default function OfferBuilder({ entityId }: { entityId: string }) {
  const [open, setOpen] = useState(false);
  const [fmv, setFmv] = useState<number | null>(null);
  const [candidate, setCandidate] = useState("");
  const [position, setPosition] = useState("");
  const [vesting, setVesting] = useState("4 years with a 1-year cliff");
  const [signatory, setSignatory] = useState("");
  const [pkgs, setPkgs] = useState<Pkg[]>([
    { salary: "", options: "", bonus: "" },
    { salary: "", options: "", bonus: "" },
  ]);
  const [note, setNote] = useState("");
  const { error, setError, guard } = useGuard();

  useEffect(() => {
    api
      .currentValuation(entityId)
      .then((v) => setFmv(v.fmv_per_share ? Number(v.fmv_per_share) : null))
      .catch(() => setFmv(null));
  }, [entityId]);

  const setPkg = (i: number, patch: Partial<Pkg>) =>
    setPkgs(pkgs.map((p, j) => (j === i ? { ...p, ...patch } : p)));

  const filled = pkgs.filter((p) => p.salary || p.options || p.bonus);
  const missing: string[] = [];
  if (!candidate) missing.push("candidate name");
  if (!position) missing.push("position");
  if (filled.length === 0) missing.push("at least one package");

  const inr = (v: string | number) => fmtMoney(v || 0);

  const packagesText = filled
    .map(
      (p, i) =>
        `PACKAGE ${i + 1}: salary INR ${Number(p.salary || 0).toLocaleString()}/yr` +
        ` | ${Number(p.options || 0).toLocaleString()} options` +
        (Number(p.bonus) ? ` | signing bonus INR ${Number(p.bonus).toLocaleString()}` : "")
    )
    .join("\n");
  const projectionText = fmv
    ? "POTENTIAL EQUITY VALUE (illustrative, before exercise cost and tax)\n" +
      filled
        .map(
          (p, i) =>
            `Package ${i + 1}: ` +
            MULTIPLES.map(
              (m) => `${m}x: INR ${(Number(p.options || 0) * fmv * m).toLocaleString()}`
            ).join(" | ")
        )
        .join("\n") +
      `\n(based on the current FMV of INR ${fmv}/share)\n`
    : "";

  return (
    <div className="card">
      <h3>
        Offer builder{" "}
        <button className="secondary" onClick={() => setOpen(!open)}>
          {open ? "Hide" : "New offer"}
        </button>
      </h3>
      <p className="muted">
        Offer 1–3 compensation packages so the candidate picks their own balance of cash and
        equity — with the equity's potential value made visible.
      </p>
      {error && <p className="error">{error}</p>}
      {note && <p>{note}</p>}

      {open && (
        <div className="row">
          <div style={{ flex: 1, minWidth: 300 }}>
            <div className="row">
              <div><label>Candidate</label><input value={candidate} onChange={(e) => setCandidate(e.target.value)} /></div>
              <div><label>Position</label><input value={position} onChange={(e) => setPosition(e.target.value)} /></div>
            </div>
            <div className="row">
              <div><label>Vesting</label><input value={vesting} onChange={(e) => setVesting(e.target.value)} /></div>
              <div><label>Signatory</label><input value={signatory} onChange={(e) => setSignatory(e.target.value)} placeholder="Founder / CEO" /></div>
            </div>
            {pkgs.map((p, i) => (
              <div className="row" key={i}>
                <div><label>Package {i + 1} — salary (₹/yr)</label><input value={p.salary} onChange={(e) => setPkg(i, { salary: e.target.value })} /></div>
                <div><label>Options</label><input value={p.options} onChange={(e) => setPkg(i, { options: e.target.value })} /></div>
                <div><label>Signing bonus (₹)</label><input value={p.bonus} onChange={(e) => setPkg(i, { bonus: e.target.value })} /></div>
              </div>
            ))}
            {pkgs.length < 3 && (
              <button className="secondary" onClick={() => setPkgs([...pkgs, { salary: "", options: "", bonus: "" }])}>
                + Add package
              </button>
            )}
            {missing.length > 0 && (
              <p className="error" style={{ marginTop: 8 }}>
                {missing.length} missing: {missing.join(", ")}
              </p>
            )}
            {fmv === null && (
              <p className="muted" style={{ marginTop: 8 }}>
                No valuation on record — add one to show the equity-value projection.
              </p>
            )}
            <div style={{ marginTop: 10 }}>
              <button
                disabled={missing.length > 0}
                onClick={guard(async () => {
                  const doc = await api.createDocument(entityId, {
                    template_key: "offer_letter_packages",
                    title: `Offer — ${candidate}`,
                    data: {
                      candidate,
                      position,
                      vesting,
                      signatory: signatory || "Authorised signatory",
                      date: new Date().toISOString().slice(0, 10),
                      packages: packagesText + "\n",
                      projection: projectionText,
                    },
                  });
                  setNote(`Offer letter generated: "${doc.title}" (see Documents).`);
                  setOpen(false);
                })}
              >
                Generate offer letter
              </button>
            </div>
          </div>

          <div style={{ flex: 1.2, minWidth: 320 }}>
            <label>Live preview</label>
            <div className="paper-sheet" style={{ fontSize: 13, padding: "22px 26px" }}>
              <div style={{ fontFamily: "Georgia, serif", fontSize: 22, fontWeight: 700 }}>
                Congratulations!
              </div>
              <p>
                {candidate || "‹candidate›"}, we are delighted to offer you the position of{" "}
                {position || "‹position›"}.
              </p>
              <div className="pkg-cards">
                {(filled.length ? filled : [{ salary: "", options: "", bonus: "" }]).map((p, i) => (
                  <div className="pkg-card" key={i}>
                    <span className="pkg-tag">Package {i + 1}</span>
                    <div className="pkg-label">Annual salary</div>
                    <div className="pkg-value">{inr(p.salary)}</div>
                    <div className="pkg-label">Equity</div>
                    <div className="pkg-value">{Number(p.options || 0).toLocaleString()} options</div>
                    <div className="pkg-label">Signing bonus</div>
                    <div className="pkg-value">{inr(p.bonus)}</div>
                  </div>
                ))}
              </div>
              <p className="muted">
                ◆ Grant type: ESOP options · ◆ Vesting: {vesting}
              </p>
              {fmv !== null && filled.length > 0 && (
                <>
                  <strong>Potential equity value</strong>
                  <table style={{ marginTop: 6 }}>
                    <thead>
                      <tr><th></th>{MULTIPLES.map((m) => <th key={m}>{m}×</th>)}</tr>
                    </thead>
                    <tbody>
                      {filled.map((p, i) => (
                        <tr key={i}>
                          <td>Package {i + 1}</td>
                          {MULTIPLES.map((m) => (
                            <td key={m}>{inr(Number(p.options || 0) * fmv * m)}</td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="muted">
                    Illustrative, at multiples of the current FMV ({fmtMoney(fmv)}/share) — before exercise
                    cost and tax.
                  </p>
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useEffect, useState } from "react";
import { fmtMoney } from "../lib/format";
import { useParams } from "react-router-dom";
import { api, type PublicFunnelInfo } from "../api";

/** Public opt-in page for a fundraising link — no login required. */
export default function Invest() {
  const { token = "" } = useParams();
  const [info, setInfo] = useState<PublicFunnelInfo | null>(null);
  const [error, setError] = useState("");
  const [done, setDone] = useState<{ data_room_granted: boolean } | null>(null);

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [firm, setFirm] = useState("");
  const [check, setCheck] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    api
      .publicFunnel(token)
      .then(setInfo)
      .catch((e) => setError((e as Error).message));
  }, [token]);

  if (error) {
    return (
      <div className="container" style={{ maxWidth: 560, margin: "60px auto" }}>
        <div className="card"><p className="error">{error}</p></div>
      </div>
    );
  }
  if (!info) return <div className="container">Loading…</div>;

  return (
    <div className="container" style={{ maxWidth: 560, margin: "60px auto" }}>
      <div style={{ textAlign: "center", marginBottom: 16, fontFamily: "var(--font-serif)", fontSize: 24, fontWeight: 700, color: "var(--heading)" }}>
        Paper
      </div>
      <div className="card">
        <h1>{info.company}</h1>
        <p className="muted">
          {info.round} round · {info.instrument?.toUpperCase()} · raising {fmtMoney(info.target_amount)}
        </p>

        {done ? (
          <>
            <h3>Thanks — you're in the loop.</h3>
            <p className="muted">
              The founders have been notified of your interest.
              {done.data_room_granted &&
                " Data-room access has been granted to your email — sign in (or sign up) with it on the investor portal to view the documents."}
            </p>
          </>
        ) : (
          <>
            <h3>Register your interest</h3>
            <label>Your name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} />
            <label>Email</label>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            <label>Firm (optional)</label>
            <input value={firm} onChange={(e) => setFirm(e.target.value)} />
            <label>Indicative check size (₹, optional)</label>
            <input value={check} onChange={(e) => setCheck(e.target.value)} />
            <label>Note to the founders (optional)</label>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} />
            <div style={{ marginTop: 12 }}>
              <button
                disabled={!name || !email}
                onClick={async () => {
                  setError("");
                  try {
                    setDone(
                      await api.publicFunnelInterest(token, {
                        name,
                        email,
                        firm: firm || null,
                        check_size: check || null,
                        notes: notes || null,
                      })
                    );
                  } catch (e) {
                    setError((e as Error).message);
                  }
                }}
              >
                Register interest
              </button>
            </div>
            {info.has_data_room && (
              <p className="muted" style={{ marginTop: 8 }}>
                Registering grants your email access to the company's data room.
              </p>
            )}
          </>
        )}
      </div>
    </div>
  );
}

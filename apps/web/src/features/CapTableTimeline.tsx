import { useEffect, useState } from "react";
import EmptyState from "../components/EmptyState";
import { api, type TimelineEvent } from "../api";

const KIND_LABEL: Record<string, string> = {
  issue: "Issuance",
  transfer: "Transfer",
  conversion: "Conversion",
  buyback: "Buy-back",
  corporate_action: "Corporate action",
  instrument: "SAFE / note",
  grant: "ESOP grant",
  exercise: "Exercise",
  valuation: "Valuation",
  round: "Round",
};

const KIND_CHIP: Record<string, string> = {
  issue: "equity",
  transfer: "ccps",
  conversion: "ccps",
  buyback: "warrant",
  corporate_action: "warrant",
  instrument: "safe",
  grant: "option_pool",
  exercise: "option_pool",
  valuation: "ccd",
  round: "equity",
};

/** Narrative equity timeline (FR-C-10) — the cap-table story as sentences,
 * newest first, Eqvista's "Timeline History" pattern. */
export default function CapTableTimeline({ entityId }: { entityId: string }) {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api
      .captableTimeline(entityId)
      .then((r) => setEvents(r.events))
      .catch((e) => setError(e.message));
  }, [entityId]);

  return (
    <div className="card">
      <h2>Timeline</h2>
      <p className="muted">
        Every equity event in plain language — issuances, transfers, SAFEs, grants,
        exercises, valuations and rounds, newest first.
      </p>
      {error && <p className="error">{error}</p>}
      {events.length === 0 ? (
        <EmptyState icon="🧭" title="No equity events yet" hint="Issuances, transfers, conversions and corporate actions appear here as a plain-language timeline." />
      ) : (
        events.map((e) => (
          <div className="timeline-row" key={`${e.kind}-${e.id}`}>
            <span className="tl-date">{e.date}</span>
            <span className={`sec-chip ${KIND_CHIP[e.kind] ?? "equity"}`}>
              {KIND_LABEL[e.kind] ?? e.kind}
            </span>
            <span>{e.text}</span>
          </div>
        ))
      )}
    </div>
  );
}

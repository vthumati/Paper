import { useState } from "react";
import Fundraising from "./Fundraising";
import ScenarioModeling from "./ScenarioModeling";
import TermSheetScanner from "./TermSheetScanner";
import Instruments from "./Instruments";
import Pipeline from "./Pipeline";

const SUBTABS = [
  { key: "rounds", label: "Rounds & funnel" },
  { key: "modeler", label: "Scenario modeler" },
  { key: "scanner", label: "Term sheet scanner" },
  { key: "instruments", label: "SAFEs & notes" },
  { key: "pipeline", label: "Pipeline (CRM)" },
] as const;

type SubTab = (typeof SUBTABS)[number]["key"];

/** The fundraising hub: one page, one job per sub-tab (Pulley-style),
 * instead of five full cards stacked into a single scroll. */
export default function FundraisingHub({
  entityId,
  onChanged,
}: {
  entityId: string;
  onChanged?: () => void;
}) {
  const [sub, setSub] = useState<SubTab>("rounds");
  return (
    <div>
      <div className="tabs subtabs">
        {SUBTABS.map((t) => (
          <button
            key={t.key}
            className={sub === t.key ? "active" : ""}
            onClick={() => setSub(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {sub === "rounds" && <Fundraising entityId={entityId} />}
      {sub === "modeler" && <ScenarioModeling entityId={entityId} />}
      {sub === "scanner" && <TermSheetScanner entityId={entityId} />}
      {sub === "instruments" && <Instruments entityId={entityId} onChanged={onChanged} />}
      {sub === "pipeline" && <Pipeline entityId={entityId} />}
    </div>
  );
}

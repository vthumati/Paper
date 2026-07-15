import { useState } from "react";
import CapTable from "./CapTable";
import CapTableAdvanced from "./CapTableAdvanced";
import RightsIssues from "./RightsIssues";

type Features = Record<string, boolean>;

const SUBTABS = [
  { key: "holdings", label: "Holdings" },
  { key: "advanced", label: "Transactions & waterfall" },
  { key: "rights", label: "Rights issues" },
] as const;

type SubTab = (typeof SUBTABS)[number]["key"];

/** Cap-table hub: holdings (incl. fully-diluted / import / export) on one
 * sub-tab, transaction mechanics and the waterfall on another. */
export default function CapTableHub({
  entityId,
  refreshKey,
  onChanged,
  features,
  showRights,
}: {
  entityId: string;
  refreshKey: number;
  onChanged: () => void;
  features: Features;
  showRights: boolean;
}) {
  const [sub, setSub] = useState<SubTab>("holdings");
  const visible = SUBTABS.filter((t) => t.key !== "rights" || showRights);
  return (
    <div>
      <div className="tabs subtabs">
        {visible.map((t) => (
          <button
            key={t.key}
            className={sub === t.key ? "active" : ""}
            onClick={() => setSub(t.key)}
          >
            {t.label}
          </button>
        ))}
      </div>
      {sub === "holdings" && (
        <CapTable
          entityId={entityId}
          refreshKey={refreshKey}
          features={{
            fully_diluted: features.fully_diluted,
            anti_dilution: features.anti_dilution,
          }}
        />
      )}
      {sub === "advanced" && (
        <CapTableAdvanced
          entityId={entityId}
          onChanged={onChanged}
          features={{
            transfers: features.transfers,
            conversions: features.conversions,
            corporate_actions: features.corporate_actions,
            founder_vesting: features.founder_vesting,
            waterfall: features.waterfall,
            demat: features.demat,
          }}
        />
      )}
      {sub === "rights" && showRights && (
        <RightsIssues entityId={entityId} onChanged={onChanged} />
      )}
    </div>
  );
}

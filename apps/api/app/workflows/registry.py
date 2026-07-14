"""Workflow definitions as data (HLD §7 / ADR-3 — rules-as-data).

Definitions are versioned and authored here as a registry. Step conditions
are pure predicates over the run context; a step whose condition returns
False is skipped when the engine reaches it (lazy evaluation), so data
collected mid-run can drive branching (e.g. foreign-investor -> FC-GPR).
"""
from collections.abc import Callable
from dataclasses import dataclass, field

from ..models.workflow import StepType


@dataclass(frozen=True)
class StepDef:
    key: str
    title: str
    type: StepType
    assignee_role: str | None = None
    condition: Callable[[dict], bool] | None = None  # include only if True/None


@dataclass(frozen=True)
class WorkflowDefinition:
    key: str
    version: int
    title: str
    steps: list[StepDef] = field(default_factory=list)


REGISTRY: dict[str, WorkflowDefinition] = {}


def register(defn: WorkflowDefinition) -> None:
    REGISTRY[defn.key] = defn


register(
    WorkflowDefinition(
        key="priced_round",
        version=1,
        title="Priced equity round",
        steps=[
            StepDef("collect_round_terms", "Collect round terms", StepType.COLLECT_INPUT, "founder"),
            StepDef("valuation", "Obtain valuation (Rule 11UA / FEMA)", StepType.EXTERNAL_CALL, "valuer"),
            StepDef("generate_documents", "Generate SHA / SSA / resolutions / PAS-4", StepType.GENERATE_DOCUMENT),
            StepDef("esign", "Collect e-signatures", StepType.REQUEST_SIGNATURE),
            StepDef("record_allotment", "Record allotment in cap table", StepType.RECORD_TRANSACTION),
            StepDef(
                "fc_gpr",
                "File FC-GPR with RBI (foreign investor present)",
                StepType.TRIGGER_FILING,
                "cs",
                condition=lambda ctx: bool(ctx.get("foreign_investor")),
            ),
            StepDef("publish_portal", "Publish holdings to investor portal", StepType.NOTIFY),
        ],
    )
)

register(
    WorkflowDefinition(
        key="incorporate_pvt_ltd",
        version=1,
        title="Incorporate Private Limited Company",
        steps=[
            StepDef("collect_promoters", "Collect promoters & directors", StepType.COLLECT_INPUT, "founder"),
            StepDef("kyc", "Run director KYC (DigiLocker / PAN)", StepType.EXTERNAL_CALL),
            StepDef("generate_spice", "Generate SPICe+ / eMoA / eAoA / AGILE-PRO", StepType.GENERATE_DOCUMENT),
            StepDef("esign", "e-Sign incorporation docs (DSC)", StepType.REQUEST_SIGNATURE),
            StepDef("file_mca", "File on MCA21 (CS)", StepType.TRIGGER_FILING, "cs"),
        ],
    )
)

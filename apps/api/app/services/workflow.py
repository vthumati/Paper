"""Workflow engine (HLD §7). A run is a state machine over an ordered list
of step instances. The first non-finished step is made ACTIVE and the run
suspends until that step is completed via the API (mirroring suspend/resume
on e-sign or filing callbacks). Steps whose condition is False are skipped."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..clock import now_ist
from ..models.workflow import (
    RunStatus,
    StepStatus,
    WorkflowRun,
    WorkflowStepInstance,
)
from ..workflows.registry import REGISTRY, WorkflowDefinition


def get_definition(key: str) -> WorkflowDefinition:
    defn = REGISTRY.get(key)
    if defn is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Unknown workflow definition '{key}'")
    return defn


def _advance(db: Session, run: WorkflowRun, defn: WorkflowDefinition) -> None:
    """Set the next eligible step ACTIVE, skipping condition-failed steps.
    Completes the run when no steps remain."""
    conditions = {s.key: s.condition for s in defn.steps}
    ctx = run.context or {}
    for st in sorted(run.steps, key=lambda x: x.order_index):
        if st.status in (StepStatus.COMPLETE, StepStatus.SKIPPED):
            continue
        cond = conditions.get(st.step_key)
        if cond is not None and not cond(ctx):
            st.status = StepStatus.SKIPPED
            continue
        st.status = StepStatus.ACTIVE
        db.flush()
        return
    run.status = RunStatus.COMPLETED
    db.flush()


def start_workflow(
    db: Session, entity_id: str, key: str, user_id: str, context: dict | None = None
) -> WorkflowRun:
    defn = get_definition(key)
    run = WorkflowRun(
        entity_id=entity_id,
        definition_key=defn.key,
        definition_version=defn.version,
        title=defn.title,
        context=context or {},
        created_by=user_id,
        status=RunStatus.RUNNING,
    )
    db.add(run)
    db.flush()
    for i, s in enumerate(defn.steps):
        db.add(
            WorkflowStepInstance(
                run_id=run.id,
                step_key=s.key,
                title=s.title,
                type=s.type,
                order_index=i,
                assignee_role=s.assignee_role,
                status=StepStatus.PENDING,
            )
        )
    db.flush()
    _advance(db, run, defn)
    db.commit()
    db.refresh(run)
    return run


def complete_step(
    db: Session, run: WorkflowRun, step_key: str, output: dict | None, user_id: str
) -> WorkflowRun:
    if run.status != RunStatus.RUNNING:
        raise HTTPException(status.HTTP_409_CONFLICT, "Workflow is not running")
    active = next((s for s in run.steps if s.status == StepStatus.ACTIVE), None)
    if active is None or active.step_key != step_key:
        raise HTTPException(
            status.HTTP_409_CONFLICT, f"Step '{step_key}' is not the active step"
        )
    active.status = StepStatus.COMPLETE
    active.output = output or {}
    active.completed_by = user_id
    active.completed_at = now_ist()
    if output:
        # reassign so SQLAlchemy detects the JSON change
        run.context = {**(run.context or {}), **output}
    _advance(db, run, get_definition(run.definition_key))
    db.commit()
    db.refresh(run)
    return run

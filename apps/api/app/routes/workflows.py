from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import (
    EntityCtx,
    RunCtx,
    entity_ctx,
    get_current_user,
    require_write,
    run_ctx,
)
from ..models.identity import User
from ..models.workflow import StepStatus, WorkflowRun
from ..schemas import (
    StepCompleteIn,
    StepDefOut,
    WorkflowDefinitionOut,
    WorkflowRunOut,
    WorkflowStartIn,
)
from ..services.workflow import complete_step, get_definition, start_workflow
from ..services.workflow_actions import apply_step_action
from ..workflows.registry import REGISTRY

router = APIRouter(tags=["workflows"])


@router.get("/workflow-definitions", response_model=list[WorkflowDefinitionOut])
def list_definitions(_: User = Depends(get_current_user)):
    return [
        WorkflowDefinitionOut(
            key=d.key,
            version=d.version,
            title=d.title,
            steps=[
                StepDefOut(key=s.key, title=s.title, type=s.type, assignee_role=s.assignee_role)
                for s in d.steps
            ],
        )
        for d in REGISTRY.values()
    ]


@router.post(
    "/entities/{entity_id}/workflows", response_model=WorkflowRunOut, status_code=201
)
def start(
    body: WorkflowStartIn,
    ctx: EntityCtx = Depends(entity_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    get_definition(body.definition_key)  # 404 early if unknown
    return start_workflow(db, ctx.entity.id, body.definition_key, user.id, body.context)


@router.get("/entities/{entity_id}/workflows", response_model=list[WorkflowRunOut])
def list_runs(ctx: EntityCtx = Depends(entity_ctx), db: Session = Depends(get_db)):
    return db.query(WorkflowRun).filter_by(entity_id=ctx.entity.id).all()


@router.get("/workflows/{run_id}", response_model=WorkflowRunOut)
def get_run(ctx: RunCtx = Depends(run_ctx)):
    return ctx.run


@router.post("/workflows/{run_id}/steps/{step_key}/complete", response_model=WorkflowRunOut)
def complete(
    step_key: str,
    body: StepCompleteIn,
    ctx: RunCtx = Depends(run_ctx),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_write(ctx.role)
    output = body.output
    active = next((s for s in ctx.run.steps if s.status == StepStatus.ACTIVE), None)
    if active is not None and active.step_key == step_key:
        # perform the step's real side-effect (e.g. generate a document) and
        # fold any produced references into the output/run context.
        output = apply_step_action(db, ctx.run, active, output, user.id)
    return complete_step(db, ctx.run, step_key, output, user.id)

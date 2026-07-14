"""Wires workflow step types to real module actions (HLD §7: the engine
orchestrates, the modules act). When a typed step is completed, this performs
the corresponding side-effect and augments the step output with references
(document_id, signature_request_id) that flow into the run context."""
from sqlalchemy.orm import Session

from ..models.document import Document
from ..models.workflow import StepType, WorkflowRun, WorkflowStepInstance
from . import document as docsvc


def apply_step_action(
    db: Session, run: WorkflowRun, step: WorkflowStepInstance, output: dict, user_id: str
) -> dict:
    out = dict(output or {})

    if step.type == StepType.GENERATE_DOCUMENT and out.get("template_key"):
        doc = docsvc.create_document(
            db,
            entity_id=run.entity_id,
            template_key=out["template_key"],
            data=out.get("data", {}),
            user_id=user_id,
            title=out.get("title"),
            subject_type="workflow_run",
            subject_id=run.id,
        )
        out["document_id"] = doc.id

    elif step.type == StepType.REQUEST_SIGNATURE and out.get("document_id") and out.get("signatories"):
        doc = db.get(Document, out["document_id"])
        if doc is not None and doc.entity_id == run.entity_id:
            sig = docsvc.create_signature(
                db, doc, out["signatories"], out.get("provider", "aadhaar_esign"), user_id
            )
            out["signature_request_id"] = sig.id

    return out

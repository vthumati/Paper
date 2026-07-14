import datetime
import enum

from sqlalchemy import JSON, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin, gen_id


class RunStatus(str, enum.Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class StepStatus(str, enum.Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETE = "complete"
    SKIPPED = "skipped"


class StepType(str, enum.Enum):
    COLLECT_INPUT = "collect_input"
    EXTERNAL_CALL = "external_call"
    GENERATE_DOCUMENT = "generate_document"
    REQUEST_SIGNATURE = "request_signature"
    RECORD_TRANSACTION = "record_transaction"
    TRIGGER_FILING = "trigger_filing"
    APPROVAL = "approval"
    NOTIFY = "notify"


class WorkflowRun(Base, TimestampMixin):
    """A running instance of a workflow definition, bound to a legal entity.
    Carries the accumulated `context` (collected step outputs) that drives
    conditional branching (HLD §7)."""

    __tablename__ = "workflow_runs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    entity_id: Mapped[str] = mapped_column(ForeignKey("legal_entities.id"), index=True)
    definition_key: Mapped[str] = mapped_column(String(64))
    definition_version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(255))
    status: Mapped[RunStatus] = mapped_column(Enum(RunStatus), default=RunStatus.RUNNING)
    context: Mapped[dict] = mapped_column(JSON, default=dict)
    created_by: Mapped[str] = mapped_column(String(32))

    steps: Mapped[list["WorkflowStepInstance"]] = relationship(
        back_populates="run",
        order_by="WorkflowStepInstance.order_index",
        cascade="all, delete-orphan",
    )


class WorkflowStepInstance(Base, TimestampMixin):
    __tablename__ = "workflow_step_instances"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=gen_id)
    run_id: Mapped[str] = mapped_column(ForeignKey("workflow_runs.id"), index=True)
    step_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(255))
    type: Mapped[StepType] = mapped_column(Enum(StepType))
    order_index: Mapped[int] = mapped_column(Integer)
    status: Mapped[StepStatus] = mapped_column(Enum(StepStatus), default=StepStatus.PENDING)
    assignee_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    output: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(32), nullable=True)
    completed_at: Mapped[datetime.datetime | None] = mapped_column(DateTime, nullable=True)

    run: Mapped[WorkflowRun] = relationship(back_populates="steps")

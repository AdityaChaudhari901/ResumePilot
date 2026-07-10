from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.schemas.common import StrictBaseModel
from app.schemas.report import InterviewQuestionGroup


class WorkflowJobKind(StrEnum):
    analysis = "analysis"
    pdf_export = "pdf_export"


class WorkflowJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    retry_scheduled = "retry_scheduled"
    cancel_requested = "cancel_requested"
    waiting_for_approval = "waiting_for_approval"
    succeeded = "succeeded"
    canceled = "canceled"
    failed = "failed"
    dead_lettered = "dead_lettered"


ACTIVE_WORKFLOW_JOB_STATUSES = frozenset(
    {
        WorkflowJobStatus.queued,
        WorkflowJobStatus.running,
        WorkflowJobStatus.retry_scheduled,
        WorkflowJobStatus.cancel_requested,
        WorkflowJobStatus.waiting_for_approval,
    }
)


TERMINAL_WORKFLOW_JOB_STATUSES = frozenset(
    {
        WorkflowJobStatus.succeeded,
        WorkflowJobStatus.canceled,
        WorkflowJobStatus.failed,
        WorkflowJobStatus.dead_lettered,
    }
)


class WorkflowJobError(StrictBaseModel):
    code: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=500)


class WorkflowApprovalDecision(StrEnum):
    approve = "approve"
    reject = "reject"


class WorkflowApprovalStatus(StrEnum):
    pending = "pending"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class LiveDraftProposal(StrictBaseModel):
    executive_summary: str = Field(min_length=1, max_length=4000)
    cover_letter: str = Field(min_length=1, max_length=12000)
    interview_questions: list[InterviewQuestionGroup] = Field(min_length=1)


class WorkflowApproval(StrictBaseModel):
    id: str = Field(pattern="^[a-f0-9]{64}$")
    kind: str = Field(default="live_ai_draft", pattern="^live_ai_draft$")
    status: WorkflowApprovalStatus
    title: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=500)
    warning_codes: list[str] = Field(default_factory=list)
    requested_at: datetime
    decision: WorkflowApprovalDecision | None = None
    decided_at: datetime | None = None
    proposal: LiveDraftProposal


class WorkflowApprovalDecisionRequest(StrictBaseModel):
    approval_id: str = Field(pattern="^[a-f0-9]{64}$")
    decision: WorkflowApprovalDecision


class WorkflowJobResponse(StrictBaseModel):
    id: str = Field(min_length=36, max_length=36)
    kind: WorkflowJobKind
    status: WorkflowJobStatus
    stage: str = Field(min_length=1, max_length=64)
    progress_percent: int = Field(ge=0, le=100)
    attempt_count: int = Field(ge=0)
    max_attempts: int = Field(ge=1)
    cancelable: bool
    result: dict[str, Any] | None = None
    approval: WorkflowApproval | None = None
    error: WorkflowJobError | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowJobListResponse(StrictBaseModel):
    items: list[WorkflowJobResponse] = Field(default_factory=list)
    count: int = Field(ge=0)

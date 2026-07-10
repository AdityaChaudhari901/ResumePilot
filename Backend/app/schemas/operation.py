from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from app.schemas.common import StrictBaseModel


class WorkflowJobKind(StrEnum):
    analysis = "analysis"
    pdf_export = "pdf_export"


class WorkflowJobStatus(StrEnum):
    queued = "queued"
    running = "running"
    retry_scheduled = "retry_scheduled"
    cancel_requested = "cancel_requested"
    succeeded = "succeeded"
    canceled = "canceled"
    failed = "failed"
    dead_lettered = "dead_lettered"


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
    error: WorkflowJobError | None = None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


class WorkflowJobListResponse(StrictBaseModel):
    items: list[WorkflowJobResponse] = Field(default_factory=list)
    count: int = Field(ge=0)

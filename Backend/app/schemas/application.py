from datetime import datetime
from enum import StrEnum

from pydantic import Field, HttpUrl, model_validator

from app.schemas.common import StrictBaseModel
from app.schemas.job import MAX_JOB_TEXT_CHARS, MIN_JOB_TEXT_CHARS, JobProfile, JobSourceType


class ApplicationStatus(StrEnum):
    draft = "draft"
    reviewed = "reviewed"
    analyzed = "analyzed"
    exported = "exported"
    applied = "applied"


class ApplicationDraftRequest(StrictBaseModel):
    source_type: JobSourceType
    job_url: HttpUrl | None = None
    job_text: str | None = Field(
        default=None,
        min_length=MIN_JOB_TEXT_CHARS,
        max_length=MAX_JOB_TEXT_CHARS,
    )
    reviewed_job_text: str = Field(
        min_length=MIN_JOB_TEXT_CHARS,
        max_length=MAX_JOB_TEXT_CHARS,
    )
    reviewed_job_profile: JobProfile
    resume_id: int | None = None

    @model_validator(mode="after")
    def validate_source(self) -> "ApplicationDraftRequest":
        if self.source_type == JobSourceType.url and self.job_url is None:
            raise ValueError("job_url is required for a URL job source")
        if self.job_text is not None and self.job_text != self.reviewed_job_text:
            raise ValueError("job_text must match reviewed_job_text")
        return self


class ApplicationStatusUpdateRequest(StrictBaseModel):
    status: ApplicationStatus


class ApplicationItem(StrictBaseModel):
    id: int
    status: ApplicationStatus
    source_type: JobSourceType
    job_url: str | None
    source_content_hash: str = Field(pattern="^[a-f0-9]{64}$")
    company: str | None
    role: str | None
    resume_id: int | None
    job_id: int | None
    analysis_id: int | None
    report_id: int | None
    match_score: float | None = Field(default=None, ge=0, le=100)
    created_at: datetime
    updated_at: datetime


class ApplicationDetail(ApplicationItem):
    reviewed_job_text: str
    reviewed_job_profile: JobProfile


class ApplicationListResponse(StrictBaseModel):
    items: list[ApplicationItem]
    count: int

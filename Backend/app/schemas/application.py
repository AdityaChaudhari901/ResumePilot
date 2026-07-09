from datetime import datetime
from enum import StrEnum

from pydantic import Field, HttpUrl

from app.schemas.common import StrictBaseModel
from app.schemas.job import JobProfile


class ApplicationStatus(StrEnum):
    draft = "draft"
    reviewed = "reviewed"
    analyzed = "analyzed"
    exported = "exported"
    applied = "applied"


class ApplicationDraftRequest(StrictBaseModel):
    job_url: HttpUrl
    reviewed_job_profile: JobProfile
    resume_id: int | None = None


class ApplicationStatusUpdateRequest(StrictBaseModel):
    status: ApplicationStatus


class ApplicationItem(StrictBaseModel):
    id: int
    status: ApplicationStatus
    job_url: str
    company: str | None
    role: str | None
    resume_id: int | None
    job_id: int | None
    analysis_id: int | None
    report_id: int | None
    match_score: float | None = Field(default=None, ge=0, le=100)
    created_at: datetime
    updated_at: datetime


class ApplicationListResponse(StrictBaseModel):
    items: list[ApplicationItem]
    count: int

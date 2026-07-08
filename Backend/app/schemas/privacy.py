from datetime import datetime

from pydantic import Field

from app.schemas.common import StrictBaseModel


class ReportDeleteResponse(StrictBaseModel):
    report_id: int
    analysis_id: int
    resume_id: int
    job_id: int
    deleted_reports: int = Field(ge=0)
    deleted_orphan_jobs: int = Field(ge=0)
    audit_event_id: int


class ResumeDeleteResponse(StrictBaseModel):
    resume_id: int
    deleted_resumes: int = Field(ge=0)
    deleted_reports: int = Field(ge=0)
    deleted_orphan_jobs: int = Field(ge=0)
    deleted_upload_files: int = Field(ge=0)
    audit_event_id: int


class RetentionPurgeResponse(StrictBaseModel):
    retention_enabled: bool
    retention_days: int | None = None
    cutoff: datetime | None = None
    deleted_resumes: int = Field(ge=0)
    deleted_reports: int = Field(ge=0)
    deleted_orphan_jobs: int = Field(ge=0)
    deleted_upload_files: int = Field(ge=0)
    audit_event_id: int | None = None

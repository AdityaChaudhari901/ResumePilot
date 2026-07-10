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
    deleted_workflow_jobs: int = Field(default=0, ge=0)
    scrubbed_workflow_jobs: int = Field(default=0, ge=0)
    deleted_export_files: int = Field(default=0, ge=0)
    audit_event_id: int


class ResumeDeleteResponse(StrictBaseModel):
    resume_id: int
    deleted_resumes: int = Field(ge=0)
    deleted_reports: int = Field(ge=0)
    deleted_orphan_jobs: int = Field(ge=0)
    deleted_upload_files: int = Field(ge=0)
    deleted_workflow_jobs: int = Field(default=0, ge=0)
    scrubbed_workflow_jobs: int = Field(default=0, ge=0)
    deleted_export_files: int = Field(default=0, ge=0)
    audit_event_id: int


class RetentionPurgeResponse(StrictBaseModel):
    retention_enabled: bool
    retention_days: int | None = None
    cutoff: datetime | None = None
    deleted_resumes: int = Field(ge=0)
    deleted_reports: int = Field(ge=0)
    deleted_orphan_jobs: int = Field(ge=0)
    deleted_upload_files: int = Field(ge=0)
    deleted_workflow_jobs: int = Field(default=0, ge=0)
    scrubbed_workflow_jobs: int = Field(default=0, ge=0)
    deleted_export_files: int = Field(default=0, ge=0)
    audit_event_id: int | None = None


class AccountDeleteResponse(StrictBaseModel):
    account_deleted: bool
    deleted_resumes: int = Field(ge=0)
    deleted_reports: int = Field(ge=0)
    deleted_jobs: int = Field(ge=0)
    deleted_applications: int = Field(ge=0)
    deleted_audit_events: int = Field(ge=0)
    deleted_usage_events: int = Field(ge=0)
    deleted_workflow_jobs: int = Field(ge=0)
    deleted_upload_files: int = Field(ge=0)
    deleted_export_files: int = Field(ge=0)

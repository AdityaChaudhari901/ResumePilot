from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AnalysisRecord,
    ApplicationRecord,
    AuditEventRecord,
    JobRecord,
    ResumeRecord,
    TailoredResumeDraftRecord,
    UsageEventRecord,
    UserRecord,
    WorkflowJobRecord,
    utc_now,
)
from app.repositories.tailored_resumes import TailoredResumeRepository
from app.schemas.application import ApplicationStatus
from app.schemas.auth import CurrentUser
from app.schemas.operation import WorkflowJobStatus
from app.schemas.privacy import (
    AccountDeleteResponse,
    ReportDeleteResponse,
    ResumeDeleteResponse,
    RetentionPurgeResponse,
)
from app.schemas.usage import UsageEventState
from app.services.audit_service import add_audit_event
from app.services.langgraph_checkpointer import delete_workflow_checkpoint
from app.services.usage_service import scrub_live_ai_usage_for_privacy


@dataclass
class DeletionCounts:
    deleted_resumes: int = 0
    deleted_reports: int = 0
    deleted_orphan_jobs: int = 0
    deleted_upload_files: int = 0
    deleted_workflow_jobs: int = 0
    scrubbed_workflow_jobs: int = 0
    deleted_export_files: int = 0

    def __add__(self, other: DeletionCounts) -> DeletionCounts:
        return DeletionCounts(
            deleted_resumes=self.deleted_resumes + other.deleted_resumes,
            deleted_reports=self.deleted_reports + other.deleted_reports,
            deleted_orphan_jobs=self.deleted_orphan_jobs + other.deleted_orphan_jobs,
            deleted_upload_files=self.deleted_upload_files + other.deleted_upload_files,
            deleted_workflow_jobs=(self.deleted_workflow_jobs + other.deleted_workflow_jobs),
            scrubbed_workflow_jobs=(self.scrubbed_workflow_jobs + other.scrubbed_workflow_jobs),
            deleted_export_files=self.deleted_export_files + other.deleted_export_files,
        )


def delete_report(
    db: Session,
    report_id: int,
    settings: Settings,
    current_user: CurrentUser,
) -> ReportDeleteResponse:
    analysis = _analysis_for_user(db, report_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    analysis_id = analysis.id
    resume_id = analysis.resume_id
    job_id = analysis.job_id
    counts = _delete_analysis_record(db, analysis, settings)
    audit_event = add_audit_event(
        db,
        event_type="report.deleted",
        user_id=current_user.id,
        payload={
            "report_id": report_id,
            "analysis_id": analysis_id,
            "resume_id": resume_id,
            "job_id": job_id,
            "deleted_reports": counts.deleted_reports,
            "deleted_orphan_jobs": counts.deleted_orphan_jobs,
            "deleted_workflow_jobs": counts.deleted_workflow_jobs,
            "scrubbed_workflow_jobs": counts.scrubbed_workflow_jobs,
            "deleted_export_files": counts.deleted_export_files,
        },
    )
    db.commit()
    return ReportDeleteResponse(
        report_id=report_id,
        analysis_id=analysis_id,
        resume_id=resume_id,
        job_id=job_id,
        deleted_reports=counts.deleted_reports,
        deleted_orphan_jobs=counts.deleted_orphan_jobs,
        deleted_workflow_jobs=counts.deleted_workflow_jobs,
        scrubbed_workflow_jobs=counts.scrubbed_workflow_jobs,
        deleted_export_files=counts.deleted_export_files,
        audit_event_id=audit_event.id,
    )


def delete_resume(
    db: Session,
    resume_id: int,
    settings: Settings,
    current_user: CurrentUser,
) -> ResumeDeleteResponse:
    resume = _resume_for_user(db, resume_id, current_user.id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    upload_path = _upload_path(settings, resume)
    deleted_upload_files = _delete_upload_file(upload_path)
    counts = _delete_resume_record(db, resume, settings)
    counts.deleted_upload_files = deleted_upload_files
    audit_event = add_audit_event(
        db,
        event_type="resume.deleted",
        user_id=current_user.id,
        payload={
            "resume_id": resume_id,
            "deleted_resumes": counts.deleted_resumes,
            "deleted_reports": counts.deleted_reports,
            "deleted_orphan_jobs": counts.deleted_orphan_jobs,
            "deleted_upload_files": counts.deleted_upload_files,
            "deleted_workflow_jobs": counts.deleted_workflow_jobs,
            "scrubbed_workflow_jobs": counts.scrubbed_workflow_jobs,
            "deleted_export_files": counts.deleted_export_files,
        },
    )
    db.commit()

    return ResumeDeleteResponse(
        resume_id=resume_id,
        deleted_resumes=counts.deleted_resumes,
        deleted_reports=counts.deleted_reports,
        deleted_orphan_jobs=counts.deleted_orphan_jobs,
        deleted_upload_files=counts.deleted_upload_files,
        deleted_workflow_jobs=counts.deleted_workflow_jobs,
        scrubbed_workflow_jobs=counts.scrubbed_workflow_jobs,
        deleted_export_files=counts.deleted_export_files,
        audit_event_id=audit_event.id,
    )


def purge_expired_records(
    db: Session,
    settings: Settings,
    current_user: CurrentUser,
) -> RetentionPurgeResponse:
    if settings.data_retention_days is None:
        return RetentionPurgeResponse(
            retention_enabled=False,
            retention_days=None,
            cutoff=None,
            deleted_resumes=0,
            deleted_reports=0,
            deleted_orphan_jobs=0,
            deleted_upload_files=0,
            deleted_workflow_jobs=0,
            scrubbed_workflow_jobs=0,
            deleted_export_files=0,
        )

    cutoff = utc_now() - timedelta(days=settings.data_retention_days)
    counts = DeletionCounts()
    expired_resumes = list(
        db.scalars(
            select(ResumeRecord).where(
                ResumeRecord.user_id == current_user.id,
                ResumeRecord.created_at < cutoff,
            )
        )
    )
    for resume in expired_resumes:
        counts.deleted_upload_files += _delete_upload_file(_upload_path(settings, resume))
        counts += _delete_resume_record(db, resume, settings)

    expired_analyses = list(
        db.scalars(
            select(AnalysisRecord).where(
                AnalysisRecord.user_id == current_user.id,
                AnalysisRecord.created_at < cutoff,
            )
        )
    )
    for analysis in expired_analyses:
        if db.get(AnalysisRecord, analysis.id):
            counts += _delete_analysis_record(db, analysis, settings)

    expired_orphan_jobs = list(
        db.scalars(
            select(JobRecord).where(
                JobRecord.user_id == current_user.id,
                JobRecord.created_at < cutoff,
            )
        )
    )
    for job in expired_orphan_jobs:
        if _analysis_count_for_job(db, job.id, user_id=current_user.id) == 0:
            _detach_application_references(db, user_id=current_user.id, job_id=job.id)
            db.delete(job)
            counts.deleted_orphan_jobs += 1

    expired_workflow_jobs = list(
        db.scalars(
            select(WorkflowJobRecord).where(
                WorkflowJobRecord.user_id == current_user.id,
                WorkflowJobRecord.created_at < cutoff,
            )
        )
    )
    counts += _delete_workflow_job_records(db, settings, expired_workflow_jobs)
    counts.deleted_export_files += _delete_expired_export_files(
        settings,
        user_id=current_user.id,
        cutoff=cutoff,
    )

    audit_event = add_audit_event(
        db,
        event_type="retention.purged",
        user_id=current_user.id,
        payload={
            "retention_days": settings.data_retention_days,
            "cutoff": cutoff.isoformat(),
            "deleted_resumes": counts.deleted_resumes,
            "deleted_reports": counts.deleted_reports,
            "deleted_orphan_jobs": counts.deleted_orphan_jobs,
            "deleted_upload_files": counts.deleted_upload_files,
            "deleted_workflow_jobs": counts.deleted_workflow_jobs,
            "scrubbed_workflow_jobs": counts.scrubbed_workflow_jobs,
            "deleted_export_files": counts.deleted_export_files,
        },
    )
    db.commit()

    return RetentionPurgeResponse(
        retention_enabled=True,
        retention_days=settings.data_retention_days,
        cutoff=cutoff,
        deleted_resumes=counts.deleted_resumes,
        deleted_reports=counts.deleted_reports,
        deleted_orphan_jobs=counts.deleted_orphan_jobs,
        deleted_upload_files=counts.deleted_upload_files,
        deleted_workflow_jobs=counts.deleted_workflow_jobs,
        scrubbed_workflow_jobs=counts.scrubbed_workflow_jobs,
        deleted_export_files=counts.deleted_export_files,
        audit_event_id=audit_event.id,
    )


def delete_account(
    db: Session,
    settings: Settings,
    current_user: CurrentUser,
) -> AccountDeleteResponse:
    """Erase all tenant-owned database rows and local files.

    File cleanup happens before the database transaction is committed so a
    storage error cannot produce a successful erasure response while leaving
    local resume or export content behind.
    """

    user = db.get(UserRecord, current_user.id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    resumes = list(db.scalars(select(ResumeRecord).where(ResumeRecord.user_id == current_user.id)))
    analyses = list(
        db.scalars(select(AnalysisRecord).where(AnalysisRecord.user_id == current_user.id))
    )
    jobs = list(db.scalars(select(JobRecord).where(JobRecord.user_id == current_user.id)))
    applications = list(
        db.scalars(select(ApplicationRecord).where(ApplicationRecord.user_id == current_user.id))
    )
    drafts = list(
        db.scalars(
            select(TailoredResumeDraftRecord).where(
                TailoredResumeDraftRecord.user_id == current_user.id
            )
        )
    )
    audit_events = list(
        db.scalars(select(AuditEventRecord).where(AuditEventRecord.user_id == current_user.id))
    )
    usage_events = list(
        db.scalars(select(UsageEventRecord).where(UsageEventRecord.user_id == current_user.id))
    )
    workflow_jobs = list(
        db.scalars(
            select(WorkflowJobRecord)
            .where(WorkflowJobRecord.user_id == current_user.id)
            .order_by(WorkflowJobRecord.id)
            .with_for_update()
        )
    )
    analyses = _lock_analysis_records(db, analyses)

    deleted_upload_files = _delete_tenant_tree(
        settings,
        settings.upload_dir / "users",
        current_user.id,
    )
    for resume in resumes:
        deleted_upload_files += _delete_upload_file(_upload_path(settings, resume))
    deleted_export_files = _delete_tenant_tree(
        settings,
        settings.export_dir,
        current_user.id,
    )

    for draft in drafts:
        db.delete(draft)
    for analysis in analyses:
        db.delete(analysis)
    db.flush()
    for application in applications:
        db.delete(application)
    for job in jobs:
        db.delete(job)
    for resume in resumes:
        db.delete(resume)
    for workflow_job in workflow_jobs:
        delete_workflow_checkpoint(settings, workflow_job.id)
        db.delete(workflow_job)
    db.flush()
    for usage_event in usage_events:
        db.delete(usage_event)
    for audit_event in audit_events:
        db.delete(audit_event)
    db.delete(user)
    db.commit()

    return AccountDeleteResponse(
        account_deleted=True,
        deleted_resumes=len(resumes),
        deleted_reports=len(analyses),
        deleted_jobs=len(jobs),
        deleted_applications=len(applications),
        deleted_audit_events=len(audit_events),
        deleted_usage_events=len(usage_events),
        deleted_workflow_jobs=len(workflow_jobs),
        deleted_upload_files=deleted_upload_files,
        deleted_export_files=deleted_export_files,
    )


def _delete_resume_record(
    db: Session,
    resume: ResumeRecord,
    settings: Settings,
) -> DeletionCounts:
    counts = DeletionCounts()
    analyses = list(resume.analyses)
    for analysis in analyses:
        counts += _delete_analysis_record(db, analysis, settings)
    queued_jobs = _workflow_jobs_for_references(
        db,
        user_id=resume.user_id,
        resume_ids={resume.id},
    )
    counts += _delete_workflow_job_records(db, settings, queued_jobs)
    _detach_application_references(db, user_id=resume.user_id, resume_id=resume.id)
    db.delete(resume)
    counts.deleted_resumes += 1
    db.flush()
    return counts


def _delete_analysis_record(
    db: Session,
    analysis: AnalysisRecord,
    settings: Settings,
) -> DeletionCounts:
    counts = DeletionCounts()
    job_id = analysis.job_id
    user_id = analysis.user_id
    workflow_jobs = _workflow_jobs_for_references(
        db,
        user_id=user_id,
        analysis_ids={analysis.id},
        report_ids={analysis.id},
        operation_ids={analysis.workflow_job_id} if analysis.workflow_job_id else set(),
    )
    workflow_jobs = _lock_workflow_job_records(db, workflow_jobs)
    locked_analyses = _lock_analysis_records(db, [analysis])
    if not locked_analyses:
        return counts
    analysis = locked_analyses[0]
    counts.deleted_reports = 1
    _detach_application_references(db, user_id=user_id, analysis_id=analysis.id)
    TailoredResumeRepository(db).delete_by_report_id(analysis.id, user_id=user_id)
    db.delete(analysis)
    db.flush()
    if _analysis_count_for_job(db, job_id, user_id=user_id) == 0:
        job = db.get(JobRecord, job_id)
        if job and job.user_id == user_id:
            _detach_application_references(db, user_id=user_id, job_id=job.id)
            db.delete(job)
            counts.deleted_orphan_jobs += 1
    counts += _delete_workflow_job_records(db, settings, workflow_jobs)
    db.flush()
    return counts


def _workflow_jobs_for_references(
    db: Session,
    *,
    user_id: int,
    analysis_ids: set[int] | None = None,
    report_ids: set[int] | None = None,
    resume_ids: set[int] | None = None,
    application_ids: set[int] | None = None,
    operation_ids: set[str] | None = None,
) -> list[WorkflowJobRecord]:
    analysis_ids = analysis_ids or set()
    report_ids = report_ids or set()
    resume_ids = resume_ids or set()
    application_ids = application_ids or set()
    operation_ids = operation_ids or set()
    records = list(
        db.scalars(select(WorkflowJobRecord).where(WorkflowJobRecord.user_id == user_id))
    )
    return [
        record
        for record in records
        if _workflow_job_references(
            record,
            analysis_ids=analysis_ids,
            report_ids=report_ids,
            resume_ids=resume_ids,
            application_ids=application_ids,
            operation_ids=operation_ids,
        )
    ]


def _workflow_job_references(
    record: WorkflowJobRecord,
    *,
    analysis_ids: set[int],
    report_ids: set[int],
    resume_ids: set[int],
    application_ids: set[int],
    operation_ids: set[str],
) -> bool:
    if (
        record.id in operation_ids
        or record.analysis_id in analysis_ids
        or record.application_id in application_ids
    ):
        return True
    for values in (record.payload_json, record.result_json):
        if not isinstance(values, dict):
            continue
        if _json_integer(values, "analysis_id") in analysis_ids:
            return True
        if _json_integer(values, "report_id") in report_ids:
            return True
        if _json_integer(values, "resume_id") in resume_ids:
            return True
        if _json_integer(values, "application_id") in application_ids:
            return True
    return False


def _json_integer(values: dict[str, object], key: str) -> int | None:
    value = values.get(key)
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _delete_workflow_job_records(
    db: Session,
    settings: Settings,
    records: list[WorkflowJobRecord],
) -> DeletionCounts:
    counts = DeletionCounts()
    for persisted in _lock_workflow_job_records(db, records):
        linked_analyses = list(
            db.scalars(select(AnalysisRecord).where(AnalysisRecord.workflow_job_id == persisted.id))
        )
        for linked_analysis in linked_analyses:
            linked_analysis.workflow_job_id = None
            db.add(linked_analysis)
        counts.deleted_export_files += _delete_workflow_artifact(settings, persisted)
        delete_workflow_checkpoint(settings, persisted.id)
        _scrub_workflow_usage(db, persisted)
        if _requires_privacy_tombstone(persisted):
            _tombstone_active_workflow_job(persisted)
            db.add(persisted)
            counts.scrubbed_workflow_jobs += 1
        else:
            db.delete(persisted)
            counts.deleted_workflow_jobs += 1
    if counts.deleted_workflow_jobs or counts.scrubbed_workflow_jobs:
        db.flush()
    return counts


def _lock_workflow_job_records(
    db: Session,
    records: list[WorkflowJobRecord],
) -> list[WorkflowJobRecord]:
    locked: list[WorkflowJobRecord] = []
    for record_id in sorted({record.id for record in records}):
        persisted = db.scalar(
            select(WorkflowJobRecord)
            .where(WorkflowJobRecord.id == record_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if persisted is not None:
            locked.append(persisted)
    return locked


def _lock_analysis_records(
    db: Session,
    records: list[AnalysisRecord],
) -> list[AnalysisRecord]:
    locked: list[AnalysisRecord] = []
    for record_id, user_id in sorted({(record.id, record.user_id) for record in records}):
        persisted = db.scalar(
            select(AnalysisRecord)
            .where(
                AnalysisRecord.id == record_id,
                AnalysisRecord.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if persisted is not None:
            locked.append(persisted)
    return locked


def _scrub_workflow_usage(db: Session, record: WorkflowJobRecord) -> None:
    usage = db.get(UsageEventRecord, record.usage_event_id)
    if usage is not None and usage.user_id == record.user_id:
        previous_state = usage.state
        if usage.state == UsageEventState.reserved.value:
            usage.state = UsageEventState.released.value
            usage.settled_at = utc_now()
        usage.reservation_key = None
        usage.metadata_json = {
            "status": "privacy_deleted",
            "previous_state": previous_state,
        }
        db.add(usage)
    scrub_live_ai_usage_for_privacy(
        db,
        user_id=record.user_id,
        operation_id=record.id,
        analysis_id=record.analysis_id,
    )


def _tombstone_active_workflow_job(record: WorkflowJobRecord) -> None:
    now = utc_now()
    record.status = WorkflowJobStatus.cancel_requested.value
    record.stage = "privacy_deletion_requested"
    record.cancel_requested_at = record.cancel_requested_at or now
    record.payload_json = {}
    record.result_json = {}
    record.error_code = None
    record.error_message = None
    record.request_id = None
    record.analysis_id = None
    record.application_id = None
    record.updated_at = now


def _requires_privacy_tombstone(record: WorkflowJobRecord) -> bool:
    if record.status == WorkflowJobStatus.running.value:
        return True
    lease_expires_at = record.lease_expires_at
    if lease_expires_at is not None and lease_expires_at.tzinfo is None:
        lease_expires_at = lease_expires_at.replace(tzinfo=UTC)
    return (
        record.status == WorkflowJobStatus.cancel_requested.value
        and lease_expires_at is not None
        and lease_expires_at > utc_now()
    )


def _detach_application_references(
    db: Session,
    *,
    user_id: int,
    analysis_id: int | None = None,
    resume_id: int | None = None,
    job_id: int | None = None,
) -> None:
    criteria = []
    if analysis_id is not None:
        criteria.extend(
            [
                ApplicationRecord.analysis_id == analysis_id,
                ApplicationRecord.report_id == analysis_id,
            ]
        )
    if resume_id is not None:
        criteria.append(ApplicationRecord.resume_id == resume_id)
    if job_id is not None:
        criteria.append(ApplicationRecord.job_id == job_id)
    if not criteria:
        return

    applications = list(
        db.scalars(
            select(ApplicationRecord).where(
                ApplicationRecord.user_id == user_id,
                or_(*criteria),
            )
        )
    )
    for application in applications:
        analysis_removed = analysis_id is not None and (
            application.analysis_id == analysis_id or application.report_id == analysis_id
        )
        if analysis_removed:
            application.analysis_id = None
            application.report_id = None
            application.match_score = None
            application.scoring_version = None
            application.score_status = None
            if application.status != ApplicationStatus.applied.value:
                application.status = ApplicationStatus.reviewed.value
        if resume_id is not None and application.resume_id == resume_id:
            application.resume_id = None
        if job_id is not None and application.job_id == job_id:
            application.job_id = None
        db.add(application)


def _analysis_count_for_job(db: Session, job_id: int, *, user_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(AnalysisRecord.id)).where(
                AnalysisRecord.job_id == job_id,
                AnalysisRecord.user_id == user_id,
            )
        )
        or 0
    )


def _resume_for_user(db: Session, resume_id: int, user_id: int) -> ResumeRecord | None:
    return db.scalar(
        select(ResumeRecord)
        .where(ResumeRecord.id == resume_id, ResumeRecord.user_id == user_id)
        .limit(1)
    )


def _analysis_for_user(db: Session, analysis_id: int, user_id: int) -> AnalysisRecord | None:
    return db.scalar(
        select(AnalysisRecord)
        .where(AnalysisRecord.id == analysis_id, AnalysisRecord.user_id == user_id)
        .limit(1)
    )


def _upload_path(settings: Settings, resume: ResumeRecord) -> Path | None:
    if not _is_sha256(resume.file_hash):
        return None
    if resume.file_extension not in settings.allowed_resume_extensions:
        return None
    file_name = f"{resume.file_hash}{resume.file_extension}"
    tenant_directory = _safe_tenant_directory(
        settings,
        settings.upload_dir / "users",
        resume.user_id,
    )
    if tenant_directory.is_symlink():
        return None
    tenant_path = tenant_directory / file_name
    if tenant_path.exists() or tenant_path.is_symlink():
        return tenant_path
    return settings.upload_dir / file_name


def _delete_upload_file(path: Path | None) -> int:
    if path is None or not (path.exists() or path.is_symlink()):
        return 0
    path.unlink()
    return 1


def _delete_workflow_artifact(settings: Settings, record: WorkflowJobRecord) -> int:
    path = _workflow_artifact_path(settings, record)
    if path is None or not (path.exists() or path.is_symlink()):
        return 0
    path.unlink()
    return 1


def _workflow_artifact_path(
    settings: Settings,
    record: WorkflowJobRecord,
) -> Path | None:
    try:
        operation_id = str(UUID(record.id))
    except (TypeError, ValueError, AttributeError):
        return None
    if operation_id != record.id.casefold():
        return None
    tenant_directory = _safe_tenant_directory(
        settings,
        settings.export_dir,
        record.user_id,
    )
    if tenant_directory.is_symlink():
        return None
    return tenant_directory / f"{operation_id}.pdf"


def _delete_expired_export_files(
    settings: Settings,
    *,
    user_id: int,
    cutoff: datetime,
) -> int:
    tenant_directory = _safe_tenant_directory(settings, settings.export_dir, user_id)
    if not tenant_directory.exists() or tenant_directory.is_symlink():
        return 0
    deleted = 0
    for path in tenant_directory.iterdir():
        if path.suffix != ".pdf" or not (path.is_file() or path.is_symlink()):
            continue
        try:
            UUID(path.stem)
        except ValueError:
            continue
        modified_at = datetime.fromtimestamp(path.lstat().st_mtime, tz=UTC)
        if modified_at < cutoff:
            path.unlink()
            deleted += 1
    _remove_empty_directory(tenant_directory)
    return deleted


def _delete_tenant_tree(settings: Settings, root: Path, user_id: int) -> int:
    tenant_directory = _safe_tenant_directory(settings, root, user_id)
    if not (tenant_directory.exists() or tenant_directory.is_symlink()):
        return 0
    return _delete_tree_without_following_symlinks(tenant_directory)


def _delete_tree_without_following_symlinks(path: Path) -> int:
    if path.is_symlink() or not path.is_dir():
        path.unlink()
        return 1
    deleted = 0
    for child in path.iterdir():
        deleted += _delete_tree_without_following_symlinks(child)
    path.rmdir()
    return deleted


def _safe_tenant_directory(settings: Settings, root: Path, user_id: int) -> Path:
    data_directory = settings.data_dir.resolve()
    root_directory = root.resolve()
    if not root_directory.is_relative_to(data_directory):
        raise RuntimeError("Storage root is outside the configured data directory")
    tenant_directory = root_directory / str(user_id)
    if tenant_directory.parent != root_directory:
        raise RuntimeError("Unsafe tenant storage path")
    return tenant_directory


def _remove_empty_directory(path: Path) -> None:
    try:
        path.rmdir()
    except OSError:
        return


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)

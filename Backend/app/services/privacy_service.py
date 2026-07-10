from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AnalysisRecord, ApplicationRecord, JobRecord, ResumeRecord, utc_now
from app.repositories.tailored_resumes import TailoredResumeRepository
from app.schemas.application import ApplicationStatus
from app.schemas.auth import CurrentUser
from app.schemas.privacy import ReportDeleteResponse, ResumeDeleteResponse, RetentionPurgeResponse
from app.services.audit_service import add_audit_event


@dataclass
class DeletionCounts:
    deleted_resumes: int = 0
    deleted_reports: int = 0
    deleted_orphan_jobs: int = 0
    deleted_upload_files: int = 0

    def __add__(self, other: DeletionCounts) -> DeletionCounts:
        return DeletionCounts(
            deleted_resumes=self.deleted_resumes + other.deleted_resumes,
            deleted_reports=self.deleted_reports + other.deleted_reports,
            deleted_orphan_jobs=self.deleted_orphan_jobs + other.deleted_orphan_jobs,
            deleted_upload_files=self.deleted_upload_files + other.deleted_upload_files,
        )


def delete_report(
    db: Session,
    report_id: int,
    current_user: CurrentUser,
) -> ReportDeleteResponse:
    analysis = _analysis_for_user(db, report_id, current_user.id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    analysis_id = analysis.id
    resume_id = analysis.resume_id
    job_id = analysis.job_id
    counts = _delete_analysis_record(db, analysis)
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
    counts = _delete_resume_record(db, resume)
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
        },
    )
    db.commit()

    return ResumeDeleteResponse(
        resume_id=resume_id,
        deleted_resumes=counts.deleted_resumes,
        deleted_reports=counts.deleted_reports,
        deleted_orphan_jobs=counts.deleted_orphan_jobs,
        deleted_upload_files=counts.deleted_upload_files,
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
        counts += _delete_resume_record(db, resume)

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
            counts += _delete_analysis_record(db, analysis)

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
        audit_event_id=audit_event.id,
    )


def _delete_resume_record(db: Session, resume: ResumeRecord) -> DeletionCounts:
    counts = DeletionCounts()
    analyses = list(resume.analyses)
    for analysis in analyses:
        counts += _delete_analysis_record(db, analysis)
    _detach_application_references(db, user_id=resume.user_id, resume_id=resume.id)
    db.delete(resume)
    counts.deleted_resumes += 1
    db.flush()
    return counts


def _delete_analysis_record(db: Session, analysis: AnalysisRecord) -> DeletionCounts:
    counts = DeletionCounts(deleted_reports=1)
    job_id = analysis.job_id
    user_id = analysis.user_id
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
    db.flush()
    return counts


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


def _upload_path(settings: Settings, resume: ResumeRecord) -> Path:
    tenant_path = (
        settings.upload_dir
        / "users"
        / str(resume.user_id)
        / f"{resume.file_hash}{resume.file_extension}"
    )
    if tenant_path.exists():
        return tenant_path
    return settings.upload_dir / f"{resume.file_hash}{resume.file_extension}"


def _delete_upload_file(path: Path) -> int:
    if not path.exists():
        return 0
    path.unlink()
    return 1

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AnalysisRecord, JobRecord, ResumeRecord, utc_now
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
) -> ReportDeleteResponse:
    analysis = db.get(AnalysisRecord, report_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")

    analysis_id = analysis.id
    resume_id = analysis.resume_id
    job_id = analysis.job_id
    counts = _delete_analysis_record(db, analysis)
    audit_event = add_audit_event(
        db,
        event_type="report.deleted",
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
) -> ResumeDeleteResponse:
    resume = db.get(ResumeRecord, resume_id)
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    upload_path = _upload_path(settings, resume)
    counts = _delete_resume_record(db, resume)
    audit_event = add_audit_event(
        db,
        event_type="resume.deleted",
        payload={
            "resume_id": resume_id,
            "deleted_resumes": counts.deleted_resumes,
            "deleted_reports": counts.deleted_reports,
            "deleted_orphan_jobs": counts.deleted_orphan_jobs,
        },
    )
    db.commit()

    counts.deleted_upload_files += _delete_upload_file(upload_path)
    if counts.deleted_upload_files:
        audit_event.payload_json = {
            **audit_event.payload_json,
            "deleted_upload_files": counts.deleted_upload_files,
        }
        db.add(audit_event)
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
    upload_paths: list[Path] = []

    expired_resumes = list(db.scalars(select(ResumeRecord).where(ResumeRecord.created_at < cutoff)))
    for resume in expired_resumes:
        upload_paths.append(_upload_path(settings, resume))
        counts += _delete_resume_record(db, resume)

    expired_analyses = list(
        db.scalars(select(AnalysisRecord).where(AnalysisRecord.created_at < cutoff))
    )
    for analysis in expired_analyses:
        if db.get(AnalysisRecord, analysis.id):
            counts += _delete_analysis_record(db, analysis)

    expired_orphan_jobs = list(db.scalars(select(JobRecord).where(JobRecord.created_at < cutoff)))
    for job in expired_orphan_jobs:
        if _analysis_count_for_job(db, job.id) == 0:
            db.delete(job)
            counts.deleted_orphan_jobs += 1

    audit_event = add_audit_event(
        db,
        event_type="retention.purged",
        payload={
            "retention_days": settings.data_retention_days,
            "cutoff": cutoff.isoformat(),
            "deleted_resumes": counts.deleted_resumes,
            "deleted_reports": counts.deleted_reports,
            "deleted_orphan_jobs": counts.deleted_orphan_jobs,
        },
    )
    db.commit()

    for upload_path in upload_paths:
        counts.deleted_upload_files += _delete_upload_file(upload_path)
    if counts.deleted_upload_files:
        audit_event.payload_json = {
            **audit_event.payload_json,
            "deleted_upload_files": counts.deleted_upload_files,
        }
        db.add(audit_event)
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
    job_ids = {analysis.job_id for analysis in analyses}
    for analysis in analyses:
        db.delete(analysis)
        counts.deleted_reports += 1
    db.delete(resume)
    counts.deleted_resumes += 1
    db.flush()

    for job_id in job_ids:
        if _analysis_count_for_job(db, job_id) == 0:
            job = db.get(JobRecord, job_id)
            if job:
                db.delete(job)
                counts.deleted_orphan_jobs += 1
    db.flush()
    return counts


def _delete_analysis_record(db: Session, analysis: AnalysisRecord) -> DeletionCounts:
    counts = DeletionCounts(deleted_reports=1)
    job_id = analysis.job_id
    db.delete(analysis)
    db.flush()
    if _analysis_count_for_job(db, job_id) == 0:
        job = db.get(JobRecord, job_id)
        if job:
            db.delete(job)
            counts.deleted_orphan_jobs += 1
    db.flush()
    return counts


def _analysis_count_for_job(db: Session, job_id: int) -> int:
    return int(
        db.scalar(select(func.count(AnalysisRecord.id)).where(AnalysisRecord.job_id == job_id)) or 0
    )


def _upload_path(settings: Settings, resume: ResumeRecord) -> Path:
    return settings.upload_dir / f"{resume.file_hash}{resume.file_extension}"


def _delete_upload_file(path: Path) -> int:
    if not path.exists():
        return 0
    path.unlink()
    return 1

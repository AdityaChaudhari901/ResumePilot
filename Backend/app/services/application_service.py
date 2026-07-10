from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import AnalysisRecord, ApplicationRecord, JobRecord, ResumeRecord
from app.repositories.applications import ApplicationRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.tailored_resumes import TailoredResumeRepository
from app.schemas.application import (
    ApplicationDraftRequest,
    ApplicationItem,
    ApplicationListResponse,
    ApplicationStatus,
    ApplicationStatusUpdateRequest,
)
from app.schemas.auth import CurrentUser
from app.schemas.job import JobAnalysisRequest
from app.services.audit_service import record_audit_event


def list_applications(
    db: Session,
    current_user: CurrentUser,
    *,
    limit: int,
) -> ApplicationListResponse:
    records = ApplicationRepository(db).list_recent(user_id=current_user.id, limit=limit)
    items = [_application_item_from_record(record) for record in records]
    return ApplicationListResponse(items=items, count=len(items))


def create_application_draft(
    db: Session,
    request: ApplicationDraftRequest,
    current_user: CurrentUser,
) -> ApplicationItem:
    if request.resume_id is not None:
        _ensure_resume_exists(db, request.resume_id, current_user)

    profile = request.reviewed_job_profile
    record = ApplicationRecord(
        user_id=current_user.id,
        source_url=str(request.job_url),
        status=ApplicationStatus.reviewed.value,
        company=profile.company,
        role=profile.role_title,
        reviewed_job_profile_json=profile.model_dump(mode="json"),
        resume_id=request.resume_id,
    )
    repository = ApplicationRepository(db)
    repository.add(record)
    saved = repository.save(record)
    record_audit_event(
        db,
        event_type="application.reviewed",
        user_id=current_user.id,
        payload={
            "application_id": saved.id,
            "resume_id": saved.resume_id,
            "source_url": saved.source_url,
            "company": saved.company,
            "role": saved.role,
        },
    )
    return _application_item_from_record(saved)


def validate_application_for_analysis(
    db: Session,
    application_id: int | None,
    current_user: CurrentUser,
) -> ApplicationRecord | None:
    if application_id is None:
        return None
    application = ApplicationRepository(db).get(application_id, user_id=current_user.id)
    if not application:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return application


def record_application_analysis(
    db: Session,
    *,
    request: JobAnalysisRequest,
    current_user: CurrentUser,
    resume: ResumeRecord,
    job: JobRecord,
    analysis: AnalysisRecord,
    application: ApplicationRecord | None,
) -> ApplicationItem:
    repository = ApplicationRepository(db)
    record = application or ApplicationRecord(
        user_id=current_user.id,
        source_url=str(request.job_url) if request.job_url else "",
        status=ApplicationStatus.draft.value,
        reviewed_job_profile_json=(request.reviewed_job_profile or job.profile_json),
    )
    previous_report_id = record.report_id
    profile_json = (
        request.reviewed_job_profile.model_dump(mode="json")
        if request.reviewed_job_profile
        else job.profile_json
    )
    record.user_id = current_user.id
    record.source_url = str(request.job_url) if request.job_url else record.source_url
    record.status = ApplicationStatus.analyzed.value
    record.company = job.company
    record.role = job.role
    record.reviewed_job_profile_json = profile_json
    record.resume_id = resume.id
    record.job_id = job.id
    record.analysis_id = analysis.id
    record.report_id = analysis.id
    record.match_score = analysis.match_score
    if record.id is None:
        repository.add(record)
    elif previous_report_id != analysis.id:
        TailoredResumeRepository(db).delete_by_application_id(record.id, user_id=current_user.id)
    saved = repository.save(record)
    record_audit_event(
        db,
        event_type="application.analyzed",
        user_id=current_user.id,
        payload={
            "application_id": saved.id,
            "resume_id": resume.id,
            "job_id": job.id,
            "analysis_id": analysis.id,
            "report_id": analysis.id,
            "match_score": analysis.match_score,
        },
    )
    return _application_item_from_record(saved)


def update_application_status(
    db: Session,
    application_id: int,
    request: ApplicationStatusUpdateRequest,
    current_user: CurrentUser,
) -> ApplicationItem:
    repository = ApplicationRepository(db)
    record = repository.get(application_id, user_id=current_user.id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    _validate_status_transition(record, request.status)
    record.status = request.status.value
    saved = repository.save(record)
    record_audit_event(
        db,
        event_type="application.status_updated",
        user_id=current_user.id,
        payload={"application_id": saved.id, "status": saved.status},
    )
    return _application_item_from_record(saved)


def mark_application_exported_for_report(
    db: Session,
    current_user: CurrentUser,
    *,
    report_id: int,
) -> None:
    repository = ApplicationRepository(db)
    record = repository.get_by_report_id(report_id, user_id=current_user.id)
    if not record or record.status == ApplicationStatus.applied.value:
        return
    record.status = ApplicationStatus.exported.value
    repository.save(record)


def _ensure_resume_exists(db: Session, resume_id: int, current_user: CurrentUser) -> None:
    if ResumeRepository(db).get(resume_id, user_id=current_user.id):
        return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")


def _validate_status_transition(
    record: ApplicationRecord,
    next_status: ApplicationStatus,
) -> None:
    if (
        next_status
        in {
            ApplicationStatus.analyzed,
            ApplicationStatus.exported,
            ApplicationStatus.applied,
        }
        and record.report_id is None
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Generate a report before moving this application to that status.",
        )


def _application_item_from_record(record: ApplicationRecord) -> ApplicationItem:
    return ApplicationItem(
        id=record.id,
        status=ApplicationStatus(record.status),
        job_url=record.source_url,
        company=record.company,
        role=record.role,
        resume_id=record.resume_id,
        job_id=record.job_id,
        analysis_id=record.analysis_id,
        report_id=record.report_id,
        match_score=record.match_score,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )

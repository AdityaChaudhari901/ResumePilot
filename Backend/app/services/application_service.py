from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import AnalysisRecord, ApplicationRecord, JobRecord, ResumeRecord
from app.repositories.analyses import AnalysisRepository
from app.repositories.applications import ApplicationRepository
from app.repositories.resumes import ResumeRepository
from app.repositories.tailored_resumes import TailoredResumeRepository
from app.schemas.application import (
    ApplicationDetail,
    ApplicationDraftRequest,
    ApplicationItem,
    ApplicationListResponse,
    ApplicationStatus,
    ApplicationStatusUpdateRequest,
)
from app.schemas.auth import CurrentUser
from app.schemas.job import JobAnalysisRequest, JobProfile, JobSourceType
from app.services.audit_service import record_audit_event
from app.services.hashing import sha256_text


def list_applications(
    db: Session,
    current_user: CurrentUser,
    *,
    limit: int,
) -> ApplicationListResponse:
    records = ApplicationRepository(db).list_recent(user_id=current_user.id, limit=limit)
    items = [_application_item_from_record(record) for record in records]
    return ApplicationListResponse(items=items, count=len(items))


def get_application(
    db: Session,
    application_id: int,
    current_user: CurrentUser,
) -> ApplicationDetail:
    record = ApplicationRepository(db).get(application_id, user_id=current_user.id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
    return _application_detail_from_record(record)


def create_application_draft(
    db: Session,
    request: ApplicationDraftRequest,
    current_user: CurrentUser,
) -> ApplicationItem:
    if request.resume_id is not None:
        _ensure_resume_exists(db, request.resume_id, current_user)

    profile = request.reviewed_job_profile
    reviewed_job_text = request.reviewed_job_text
    record = ApplicationRecord(
        user_id=current_user.id,
        source_type=request.source_type.value,
        source_url=str(request.job_url) if request.job_url else None,
        reviewed_job_text=reviewed_job_text,
        source_content_hash=sha256_text(reviewed_job_text),
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
            "source_type": saved.source_type,
            "source_content_hash": saved.source_content_hash,
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


def stage_application_analysis(
    db: Session,
    *,
    request: JobAnalysisRequest,
    current_user: CurrentUser,
    resume: ResumeRecord,
    job: JobRecord,
    analysis: AnalysisRecord,
    application: ApplicationRecord | None,
) -> ApplicationRecord:
    repository = ApplicationRepository(db)
    if application is not None and application.id is not None:
        record = repository.get_for_update(application.id, user_id=current_user.id)
        if record is None:
            raise RuntimeError("Application disappeared during analysis finalization")
    else:
        record = repository.get_by_report_id_for_update(
            analysis.id,
            user_id=current_user.id,
        )
    if record is not None and _linked_to_newer_analysis(
        db,
        record,
        analysis=analysis,
        user_id=current_user.id,
    ):
        return record
    record = record or ApplicationRecord(
        user_id=current_user.id,
        source_type=(
            JobSourceType.url.value if request.job_url else JobSourceType.pasted_text.value
        ),
        source_url=str(request.job_url) if request.job_url else None,
        reviewed_job_text=job.raw_text,
        source_content_hash=job.content_hash,
        status=ApplicationStatus.draft.value,
        reviewed_job_profile_json=(
            request.reviewed_job_profile.model_dump(mode="json")
            if request.reviewed_job_profile
            else job.profile_json
        ),
    )
    previous_report_id = record.report_id
    profile_json = (
        request.reviewed_job_profile.model_dump(mode="json")
        if request.reviewed_job_profile
        else job.profile_json
    )
    record.user_id = current_user.id
    record.status = ApplicationStatus.analyzed.value
    record.company = job.company
    record.role = job.role
    record.reviewed_job_profile_json = profile_json
    record.resume_id = resume.id
    record.job_id = job.id
    record.analysis_id = analysis.id
    record.report_id = analysis.id
    record.match_score = analysis.match_score
    if record.id is not None and previous_report_id != analysis.id:
        TailoredResumeRepository(db).delete_by_application_id(record.id, user_id=current_user.id)
    repository.add(record)
    return record


def _linked_to_newer_analysis(
    db: Session,
    application: ApplicationRecord,
    *,
    analysis: AnalysisRecord,
    user_id: int,
) -> bool:
    if application.report_id is None or application.report_id == analysis.id:
        return False
    linked_analysis = AnalysisRepository(db).get(application.report_id, user_id=user_id)
    if linked_analysis is None:
        raise RuntimeError("Application references an analysis that no longer exists")
    return (linked_analysis.created_at, linked_analysis.id) > (
        analysis.created_at,
        analysis.id,
    )


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
        source_type=JobSourceType(record.source_type),
        job_url=record.source_url,
        source_content_hash=record.source_content_hash,
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


def _application_detail_from_record(record: ApplicationRecord) -> ApplicationDetail:
    item = _application_item_from_record(record)
    return ApplicationDetail(
        **item.model_dump(),
        reviewed_job_text=record.reviewed_job_text,
        reviewed_job_profile=JobProfile.model_validate(record.reviewed_job_profile_json),
    )

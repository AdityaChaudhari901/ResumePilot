from collections.abc import Callable
from urllib.parse import urlparse

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_cached_settings
from app.db.models import (
    AnalysisRecord,
    ApplicationRecord,
    JobRecord,
    ResumeRecord,
    UsageEventRecord,
    default_workflow_trace,
)
from app.repositories.analyses import AnalysisRepository
from app.repositories.jobs import JobRepository
from app.repositories.resumes import ResumeRepository
from app.schemas.agent import AgentWorkflowTrace, ReportWorkflowTraceResponse
from app.schemas.auth import CurrentUser
from app.schemas.common import ValidationWarning
from app.schemas.job import (
    JobAnalysisRequest,
    JobAnalysisResponse,
    JobPreviewQualityCheck,
    JobPreviewRequest,
    JobPreviewResponse,
    JobPreviewStatus,
    JobProfile,
    JobSourceType,
)
from app.schemas.report import ApplicationReport, ReportHistoryItem, ReportHistoryResponse
from app.schemas.resume import ResumeProfile
from app.services.agent_workflow import run_application_agent_workflow
from app.services.analysis_finalization_service import (
    finalize_analysis_transaction,
    require_active_analysis_workflow_lease,
)
from app.services.application_service import validate_application_for_analysis
from app.services.audit_service import record_audit_event
from app.services.file_storage import StoredUpload, persist_resume_upload
from app.services.job_parser import fetch_job_text, job_content_hash, parse_job_profile
from app.services.matcher import match_resume_to_job
from app.services.resume_parser import ResumeParseError, extract_resume_text, parse_resume_profile
from app.services.usage_service import (
    release_usage_reservation,
    reserve_analysis_usage,
)

MIN_CONFIDENT_PREVIEW_TEXT_CHARS = 160


def create_resume_from_upload(
    db: Session, upload: StoredUpload, current_user: CurrentUser
) -> ResumeRecord:
    resumes = ResumeRepository(db)
    existing = resumes.get_by_file_hash(upload.file_hash, user_id=current_user.id)
    if existing:
        record_audit_event(
            db,
            event_type="resume.reused",
            user_id=current_user.id,
            payload={
                "resume_id": existing.id,
                "file_extension": existing.file_extension,
                "content_type": existing.content_type,
            },
        )
        return existing

    try:
        raw_text = extract_resume_text(upload.content, upload.extension)
        profile = parse_resume_profile(raw_text, resume_id=0)
    except ResumeParseError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    record = ResumeRecord(
        user_id=current_user.id,
        file_name=upload.original_name,
        file_extension=upload.extension,
        file_hash=upload.file_hash,
        content_type=upload.content_type,
        raw_text=raw_text,
        profile_json=profile.model_dump(mode="json"),
        candidate_name=profile.candidate.name,
        candidate_email=str(profile.candidate.email) if profile.candidate.email else None,
    )
    resumes.add(record)

    profile.resume_id = record.id
    record.profile_json = profile.model_dump(mode="json")
    saved = resumes.save(record)
    try:
        persist_resume_upload(upload)
    except OSError as exc:
        db.delete(saved)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Resume could not be stored safely",
        ) from exc
    record_audit_event(
        db,
        event_type="resume.uploaded",
        user_id=current_user.id,
        payload={
            "resume_id": saved.id,
            "file_extension": saved.file_extension,
            "content_type": saved.content_type,
            "warnings_count": len(profile.warnings),
        },
    )
    return saved


def analyze_job(
    db: Session,
    request: JobAnalysisRequest,
    current_user: CurrentUser,
    settings: Settings | None = None,
    *,
    analysis_usage: UsageEventRecord | None = None,
    workflow_job_id: str | None = None,
    workflow_lease_owner: str | None = None,
    release_usage_on_failure: bool = True,
    progress_callback: Callable[[str, int], None] | None = None,
) -> JobAnalysisResponse:
    resolved_settings = settings or get_cached_settings()
    resumes = ResumeRepository(db)
    jobs = JobRepository(db)
    analyses = AnalysisRepository(db)

    if workflow_job_id:
        require_active_analysis_workflow_lease(
            db,
            workflow_job_id=workflow_job_id,
            user_id=current_user.id,
            lease_owner=workflow_lease_owner,
        )
        existing = analyses.get_by_workflow_job_id_for_update(
            workflow_job_id,
            user_id=current_user.id,
        )
        if existing and existing.status == "completed":
            if existing.resume_id != request.resume_id:
                raise RuntimeError("Completed workflow analysis does not match its request")
            replay_resume = resumes.get(existing.resume_id, user_id=current_user.id)
            replay_job = jobs.get(existing.job_id, user_id=current_user.id)
            if replay_resume is None or replay_job is None:
                raise RuntimeError("Completed workflow analysis dependencies are missing")
            replay_application = validate_application_for_analysis(
                db,
                request.application_id,
                current_user,
            )
            repaired = finalize_analysis_transaction(
                db,
                request=request,
                current_user=current_user,
                resume=replay_resume,
                job=replay_job,
                analysis=existing,
                application=replay_application,
                analysis_usage=analysis_usage,
                workflow_lease_owner=workflow_lease_owner,
            )
            return _analysis_response(repaired)
        if existing:
            db.delete(existing)
            db.commit()
        else:
            db.commit()

    resume_record = resumes.get(request.resume_id, user_id=current_user.id)
    if not resume_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    application_record = validate_application_for_analysis(db, request.application_id, current_user)
    if analysis_usage is None:
        analysis_usage = reserve_analysis_usage(db, current_user)

    analysis_record: AnalysisRecord | None = None
    try:
        _report_progress(progress_callback, "fetching_job", 15)
        resume = ResumeProfile.model_validate(resume_record.profile_json)
        raw_job_text = _job_text_from_request(
            request,
            resolved_settings,
            application=application_record,
        )
        content_hash = job_content_hash(raw_job_text)
        if application_record and application_record.source_content_hash != content_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The reviewed job snapshot changed. Reopen the application and retry.",
            )
        reviewed_profile = (
            JobProfile.model_validate(application_record.reviewed_job_profile_json)
            if application_record
            else request.reviewed_job_profile
        )
        source_url = (
            application_record.source_url
            if application_record
            else str(request.job_url)
            if request.job_url
            else None
        )
        _report_progress(progress_callback, "parsing_job", 30)
        job_record = _create_job_record(
            jobs,
            raw_job_text,
            content_hash,
            request,
            current_user=current_user,
            reviewed_profile=reviewed_profile,
            source_url=source_url,
        )
        job = JobProfile.model_validate(job_record.profile_json)

        _report_progress(progress_callback, "matching_evidence", 45)
        match = match_resume_to_job(resume, job)
        analysis_record = AnalysisRecord(
            user_id=current_user.id,
            resume_id=resume_record.id,
            job_id=job_record.id,
            workflow_job_id=workflow_job_id,
            status="running",
            match_score=match.score,
            match_result_json=match.model_dump(mode="json"),
            report_json={},
            report_markdown="",
            validation_warnings_json=[],
        )
        analyses.add(analysis_record)
        _report_progress(progress_callback, "generating_report", 60)

        workflow_result = run_application_agent_workflow(
            analysis_id=analysis_record.id,
            resume=resume,
            job=job,
            match=match,
            settings=resolved_settings,
        )
        _report_progress(progress_callback, "validating_claims", 80)
        _report_progress(progress_callback, "saving_application", 90)

        analysis_record = finalize_analysis_transaction(
            db,
            request=request,
            current_user=current_user,
            resume=resume_record,
            job=job_record,
            analysis=analysis_record,
            application=application_record,
            analysis_usage=analysis_usage,
            workflow_result=workflow_result,
            workflow_lease_owner=workflow_lease_owner,
        )
        return _analysis_response(analysis_record)
    except Exception:
        analysis_id = analysis_record.id if analysis_record is not None else None
        db.rollback()
        lease_allows_failure_write = True
        if workflow_job_id is not None:
            try:
                require_active_analysis_workflow_lease(
                    db,
                    workflow_job_id=workflow_job_id,
                    user_id=current_user.id,
                    lease_owner=workflow_lease_owner,
                )
            except RuntimeError:
                db.rollback()
                lease_allows_failure_write = False
        persisted_analysis = (
            analyses.get(analysis_id, user_id=current_user.id) if analysis_id is not None else None
        )
        if (
            lease_allows_failure_write
            and persisted_analysis is not None
            and persisted_analysis.status != "completed"
        ):
            persisted_analysis.status = "failed"
            persisted_analysis.workflow_mode = "deterministic_fallback"
            analyses.save(persisted_analysis)
        elif (
            lease_allows_failure_write
            and persisted_analysis is None
            and analysis_record is not None
            and workflow_job_id is None
        ):
            analysis_record.status = "failed"
            analysis_record.workflow_mode = "deterministic_fallback"
            analyses.save(analysis_record)
        elif workflow_job_id is not None:
            db.rollback()
        if release_usage_on_failure:
            persisted_usage = (
                db.get(UsageEventRecord, analysis_usage.id)
                if analysis_usage.id is not None
                else analysis_usage
            )
            release_usage_reservation(
                db,
                persisted_usage or analysis_usage,
                runtime_status="failed",
                metadata={
                    "analysis_id": analysis_id,
                    "operation_id": workflow_job_id,
                },
            )
        raise


def preview_job(
    request: JobPreviewRequest,
    settings: Settings | None = None,
) -> JobPreviewResponse:
    resolved_settings = settings or get_cached_settings()
    source_type = JobSourceType.url if request.job_url else JobSourceType.pasted_text
    parser_name = (
        _parser_name_for_url(str(request.job_url))
        if request.job_url
        else JobSourceType.pasted_text.value
    )
    if request.job_text:
        raw_job_text = request.job_text
    else:
        try:
            raw_job_text = fetch_job_text(str(request.job_url), settings=resolved_settings)
        except HTTPException as exc:
            preview_status = _preview_status_from_fetch_error(exc)
            message = _preview_error_message(preview_status, exc)
            return JobPreviewResponse(
                source_type=source_type,
                job_url=request.job_url,
                reviewed_job_text=None,
                source_content_hash=None,
                profile=JobProfile(
                    job_id=0,
                    warnings=[_preview_warning(preview_status.value, message)],
                ),
                raw_text_char_count=0,
                status=preview_status,
                parser=parser_name,
                quality_checks=[
                    JobPreviewQualityCheck(
                        code=preview_status.value,
                        status="fail",
                        message=message,
                    )
                ],
            )

    profile = parse_job_profile(raw_job_text, job_id=0)
    quality_checks = _job_preview_quality_checks(profile, raw_text_length=len(raw_job_text))
    return JobPreviewResponse(
        source_type=source_type,
        job_url=request.job_url,
        reviewed_job_text=raw_job_text,
        source_content_hash=job_content_hash(raw_job_text),
        profile=profile,
        raw_text_char_count=len(raw_job_text),
        status=_job_preview_status(quality_checks),
        parser=parser_name,
        quality_checks=quality_checks,
    )


def latest_resume(db: Session, current_user: CurrentUser) -> ResumeRecord | None:
    return ResumeRepository(db).latest(user_id=current_user.id)


def get_resume_profile(db: Session, resume_id: int, current_user: CurrentUser) -> ResumeProfile:
    resume_record = ResumeRepository(db).get(resume_id, user_id=current_user.id)
    if not resume_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")
    return ResumeProfile.model_validate(resume_record.profile_json)


def list_report_history(
    db: Session,
    current_user: CurrentUser,
    *,
    limit: int = 20,
) -> ReportHistoryResponse:
    analyses = AnalysisRepository(db).list_recent(user_id=current_user.id, limit=limit)
    return ReportHistoryResponse(
        items=[_report_history_item_from_record(analysis) for analysis in analyses]
    )


def get_report(db: Session, report_id: int, current_user: CurrentUser) -> ApplicationReport:
    analysis = AnalysisRepository(db).get(report_id, user_id=current_user.id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return ApplicationReport.model_validate(analysis.report_json)


def get_report_markdown(db: Session, report_id: int, current_user: CurrentUser) -> str:
    analysis = AnalysisRepository(db).get(report_id, user_id=current_user.id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return analysis.report_markdown


def ensure_report_access(db: Session, report_id: int, current_user: CurrentUser) -> None:
    analysis = AnalysisRepository(db).get(report_id, user_id=current_user.id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")


def get_report_trace(
    db: Session, report_id: int, current_user: CurrentUser
) -> ReportWorkflowTraceResponse:
    analysis = AnalysisRepository(db).get(report_id, user_id=current_user.id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return ReportWorkflowTraceResponse(
        analysis_id=analysis.id,
        report_id=analysis.id,
        trace=_workflow_trace_from_record(analysis),
    )


def _parser_name_for_url(job_url: str) -> str:
    hostname = urlparse(job_url).hostname or ""
    if "greenhouse.io" in hostname:
        return "greenhouse"
    if "lever.co" in hostname:
        return "lever"
    if "rippling.com" in hostname:
        return "rippling"
    if "myworkdayjobs.com" in hostname or "workdayjobs.com" in hostname:
        return "workday"
    return "generic_html"


def _preview_status_from_fetch_error(exc: HTTPException) -> JobPreviewStatus:
    detail = str(exc.detail).lower()
    if any(marker in detail for marker in ("blocked", "private", "rate limited")):
        return JobPreviewStatus.blocked_private
    if "could not fetch" in detail:
        return JobPreviewStatus.needs_review
    return JobPreviewStatus.too_short


def _preview_error_message(preview_status: JobPreviewStatus, exc: HTTPException) -> str:
    if preview_status == JobPreviewStatus.blocked_private:
        return (
            "This listing is private, blocked, or rate limited. Use a public job listing URL "
            "that exposes readable role requirements."
        )
    if preview_status == JobPreviewStatus.too_short:
        return (
            "The listing did not expose enough readable job text. Use a public job listing URL "
            "with visible requirements and responsibilities."
        )
    return f"ResumePilot could not fetch this listing. Check the URL and try again. ({exc.detail})"


def _job_preview_quality_checks(
    profile: JobProfile, *, raw_text_length: int
) -> list[JobPreviewQualityCheck]:
    checks = [
        JobPreviewQualityCheck(
            code="readable_text",
            status="pass" if raw_text_length >= MIN_CONFIDENT_PREVIEW_TEXT_CHARS else "fail",
            message=(
                "Job page has enough readable text."
                if raw_text_length >= MIN_CONFIDENT_PREVIEW_TEXT_CHARS
                else "Job page readable text is short; extraction may be incomplete."
            ),
        ),
        JobPreviewQualityCheck(
            code="required_or_preferred_skills",
            status="pass" if profile.required_skills or profile.preferred_skills else "fail",
            message=(
                "Required or preferred skills were extracted."
                if profile.required_skills or profile.preferred_skills
                else "No explicit required or preferred skills were extracted."
            ),
        ),
        JobPreviewQualityCheck(
            code="role_and_company",
            status="pass" if profile.role_title and profile.company else "warn",
            message=(
                "Role and company were extracted."
                if profile.role_title and profile.company
                else "Role or company could not be extracted confidently."
            ),
        ),
    ]
    return checks


def _job_preview_status(checks: list[JobPreviewQualityCheck]) -> JobPreviewStatus:
    failing_codes = {check.code for check in checks if check.status == "fail"}
    warning_codes = {check.code for check in checks if check.status == "warn"}
    if "required_or_preferred_skills" in failing_codes:
        return JobPreviewStatus.missing_requirements
    if "readable_text" in failing_codes:
        return JobPreviewStatus.too_short
    if warning_codes:
        return JobPreviewStatus.needs_review
    return JobPreviewStatus.ready


def _preview_warning(code: str, message: str) -> ValidationWarning:
    return ValidationWarning(code=code, message=message)


def _job_text_from_request(
    request: JobAnalysisRequest,
    settings: Settings,
    *,
    application: ApplicationRecord | None,
) -> str:
    if application:
        return application.reviewed_job_text
    if request.job_text:
        return request.job_text
    if request.job_url:
        return fetch_job_text(str(request.job_url), settings=settings)
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Either application_id, job_text, or job_url is required",
    )


def _create_job_record(
    jobs: JobRepository,
    raw_job_text: str,
    content_hash: str,
    request: JobAnalysisRequest,
    *,
    current_user: CurrentUser,
    reviewed_profile: JobProfile | None,
    source_url: str | None,
) -> JobRecord:
    existing = jobs.get_by_source_snapshot(
        content_hash,
        user_id=current_user.id,
        source_url=source_url,
    )
    if existing:
        return existing

    profile = reviewed_profile or parse_job_profile(
        raw_job_text,
        job_id=0,
        company=request.company,
        role=request.role,
    )
    record = JobRecord(
        user_id=current_user.id,
        source_url=source_url,
        content_hash=content_hash,
        company=profile.company,
        role=profile.role_title,
        raw_text=raw_job_text,
        profile_json=profile.model_dump(mode="json"),
    )
    jobs.add(record)
    profile.job_id = record.id
    record.profile_json = profile.model_dump(mode="json")
    return jobs.save(record)


def _workflow_trace_from_record(analysis: AnalysisRecord) -> AgentWorkflowTrace:
    trace_json = analysis.workflow_trace_json or default_workflow_trace()
    try:
        return AgentWorkflowTrace.model_validate(trace_json)
    except ValidationError:
        return AgentWorkflowTrace.model_validate(default_workflow_trace())


def _analysis_response(analysis: AnalysisRecord) -> JobAnalysisResponse:
    return JobAnalysisResponse(
        analysis_id=analysis.id,
        report_id=analysis.id,
        match_score=analysis.match_score,
        status=analysis.status,
    )


def _report_progress(
    callback: Callable[[str, int], None] | None,
    stage: str,
    progress: int,
) -> None:
    if callback:
        callback(stage, progress)


def _report_history_item_from_record(analysis: AnalysisRecord) -> ReportHistoryItem:
    counts = _report_history_counts_from_record(analysis)
    return ReportHistoryItem(
        report_id=analysis.id,
        analysis_id=analysis.id,
        resume_id=analysis.resume_id,
        job_id=analysis.job_id,
        company=analysis.job.company,
        role=analysis.job.role,
        resume_candidate_name=analysis.resume.candidate_name,
        status=analysis.status,
        match_score=analysis.match_score,
        workflow_mode=analysis.workflow_mode,
        validation_warnings_count=counts["validation_warnings"],
        matched_skills_count=counts["matched_skills"],
        missing_skills_count=counts["missing_skills"],
        weak_skills_count=counts["weak_skills"],
        created_at=analysis.created_at,
    )


def _report_history_counts_from_record(analysis: AnalysisRecord) -> dict[str, int]:
    try:
        report = ApplicationReport.model_validate(analysis.report_json)
    except ValidationError:
        match_result = analysis.match_result_json or {}
        return {
            "validation_warnings": len(analysis.validation_warnings_json or []),
            "matched_skills": len(match_result.get("matched_skills") or []),
            "missing_skills": len(match_result.get("missing_skills") or []),
            "weak_skills": len(match_result.get("weak_skills") or []),
        }
    return {
        "validation_warnings": len(report.validation_warnings),
        "matched_skills": len(report.matched_skills),
        "missing_skills": len(report.missing_skills),
        "weak_skills": len(report.weak_skills),
    }

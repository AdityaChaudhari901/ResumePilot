from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import Settings, get_cached_settings
from app.db.models import AnalysisRecord, JobRecord, ResumeRecord, default_workflow_trace
from app.repositories.analyses import AnalysisRepository
from app.repositories.jobs import JobRepository
from app.repositories.resumes import ResumeRepository
from app.schemas.agent import AgentWorkflowTrace, ReportWorkflowTraceResponse
from app.schemas.job import JobAnalysisRequest, JobAnalysisResponse, JobProfile
from app.schemas.report import ApplicationReport
from app.schemas.resume import ResumeProfile
from app.services.agent_workflow import run_application_agent_workflow
from app.services.file_storage import StoredUpload
from app.services.job_parser import fetch_job_text, job_content_hash, parse_job_profile
from app.services.latex_resume_renderer import render_tailored_resume_latex
from app.services.matcher import match_resume_to_job
from app.services.report_generator import report_to_markdown
from app.services.resume_parser import extract_resume_text, parse_resume_profile


def create_resume_from_upload(db: Session, upload: StoredUpload) -> ResumeRecord:
    resumes = ResumeRepository(db)
    existing = resumes.get_by_file_hash(upload.file_hash)
    if existing:
        return existing

    raw_text = extract_resume_text(upload.content, upload.extension)
    profile = parse_resume_profile(raw_text, resume_id=0)
    record = ResumeRecord(
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
    return resumes.save(record)


def analyze_job(
    db: Session,
    request: JobAnalysisRequest,
    settings: Settings | None = None,
) -> JobAnalysisResponse:
    resolved_settings = settings or get_cached_settings()
    resumes = ResumeRepository(db)
    jobs = JobRepository(db)
    analyses = AnalysisRepository(db)

    resume_record = resumes.get(request.resume_id)
    if not resume_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    resume = ResumeProfile.model_validate(resume_record.profile_json)
    raw_job_text = _job_text_from_request(request)
    content_hash = job_content_hash(raw_job_text)
    job_record = _create_job_record(jobs, raw_job_text, content_hash, request)
    job = JobProfile.model_validate(job_record.profile_json)

    match = match_resume_to_job(resume, job)
    analysis_record = AnalysisRecord(
        resume_id=resume_record.id,
        job_id=job_record.id,
        status="running",
        match_score=match.score,
        match_result_json=match.model_dump(mode="json"),
        report_json={},
        report_markdown="",
        validation_warnings_json=[],
    )
    analyses.add(analysis_record)

    workflow_result = run_application_agent_workflow(
        analysis_id=analysis_record.id,
        resume=resume,
        job=job,
        match=match,
        settings=resolved_settings,
    )
    report = workflow_result.report
    markdown = report_to_markdown(report)

    analysis_record.status = "completed"
    analysis_record.report_json = report.model_dump(mode="json")
    analysis_record.report_markdown = markdown
    analysis_record.validation_warnings_json = [
        warning.model_dump(mode="json") for warning in report.validation_warnings
    ]
    analysis_record.workflow_mode = workflow_result.trace.mode.value
    analysis_record.workflow_trace_json = workflow_result.trace.model_dump(mode="json")
    analyses.save(analysis_record)

    return JobAnalysisResponse(
        analysis_id=analysis_record.id,
        report_id=analysis_record.id,
        match_score=analysis_record.match_score,
        status=analysis_record.status,
    )


def latest_resume(db: Session) -> ResumeRecord | None:
    return ResumeRepository(db).latest()


def get_report(db: Session, report_id: int) -> ApplicationReport:
    analysis = AnalysisRepository(db).get(report_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return ApplicationReport.model_validate(analysis.report_json)


def get_report_markdown(db: Session, report_id: int) -> str:
    analysis = AnalysisRepository(db).get(report_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return analysis.report_markdown


def get_report_trace(db: Session, report_id: int) -> ReportWorkflowTraceResponse:
    analysis = AnalysisRepository(db).get(report_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return ReportWorkflowTraceResponse(
        analysis_id=analysis.id,
        report_id=analysis.id,
        trace=_workflow_trace_from_record(analysis),
    )


def get_tailored_resume_latex(db: Session, report_id: int) -> str:
    analysis = AnalysisRepository(db).get(report_id)
    if not analysis:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    report = ApplicationReport.model_validate(analysis.report_json)
    resume = ResumeProfile.model_validate(analysis.resume.profile_json)
    job = JobProfile.model_validate(analysis.job.profile_json)
    return render_tailored_resume_latex(report=report, resume=resume, job=job)


def _job_text_from_request(request: JobAnalysisRequest) -> str:
    if request.job_text:
        return request.job_text
    if request.job_url:
        return fetch_job_text(str(request.job_url))
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST, detail="Either job_text or job_url is required"
    )


def _create_job_record(
    jobs: JobRepository,
    raw_job_text: str,
    content_hash: str,
    request: JobAnalysisRequest,
) -> JobRecord:
    existing = jobs.get_by_content_hash(content_hash)
    if existing:
        return existing

    profile = parse_job_profile(
        raw_job_text,
        job_id=0,
        company=request.company,
        role=request.role,
    )
    record = JobRecord(
        source_url=str(request.job_url) if request.job_url else None,
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

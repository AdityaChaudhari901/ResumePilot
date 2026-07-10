from sqlalchemy.orm import Session

from app.db.models import (
    AnalysisRecord,
    ApplicationRecord,
    JobRecord,
    ResumeRecord,
    UsageEventRecord,
)
from app.repositories.analyses import AnalysisRepository
from app.repositories.usage_events import UsageEventRepository
from app.repositories.workflow_jobs import WorkflowJobRepository
from app.schemas.agent import AgentWorkflowResult
from app.schemas.auth import CurrentUser
from app.schemas.job import JobAnalysisRequest
from app.schemas.report import ApplicationReport
from app.services.application_service import stage_application_analysis
from app.services.audit_service import ensure_analysis_audit_event
from app.services.report_generator import report_to_markdown
from app.services.usage_service import stage_analysis_usage_finalization


def finalize_analysis_transaction(
    db: Session,
    *,
    request: JobAnalysisRequest,
    current_user: CurrentUser,
    resume: ResumeRecord,
    job: JobRecord,
    analysis: AnalysisRecord,
    application: ApplicationRecord | None,
    analysis_usage: UsageEventRecord | None,
    workflow_result: AgentWorkflowResult | None = None,
    workflow_lease_owner: str | None = None,
) -> AnalysisRecord:
    """Commit the complete analysis result once, or repair it idempotently on replay."""

    require_active_analysis_workflow_lease(
        db,
        workflow_job_id=analysis.workflow_job_id,
        user_id=current_user.id,
        lease_owner=workflow_lease_owner,
    )
    locked_analysis = AnalysisRepository(db).get_for_update(
        analysis.id,
        user_id=current_user.id,
    )
    if locked_analysis is None:
        raise RuntimeError("Analysis disappeared during finalization")

    report = _complete_or_validate_analysis(
        locked_analysis,
        workflow_result=workflow_result,
    )
    _validate_finalization_context(
        report=report,
        current_user=current_user,
        resume=resume,
        job=job,
        analysis=locked_analysis,
        application=application,
        analysis_usage=analysis_usage,
    )
    linked_application = stage_application_analysis(
        db,
        request=request,
        current_user=current_user,
        resume=resume,
        job=job,
        analysis=locked_analysis,
        application=application,
    )
    ensure_analysis_audit_event(
        db,
        event_type="application.analyzed",
        user_id=current_user.id,
        analysis_id=locked_analysis.id,
        payload={
            "application_id": linked_application.id,
            "resume_id": resume.id,
            "job_id": job.id,
            "analysis_id": locked_analysis.id,
            "report_id": locked_analysis.id,
            "match_score": locked_analysis.match_score,
        },
    )
    ensure_analysis_audit_event(
        db,
        event_type="job.analyzed",
        user_id=current_user.id,
        analysis_id=locked_analysis.id,
        payload={
            "analysis_id": locked_analysis.id,
            "report_id": locked_analysis.id,
            "resume_id": resume.id,
            "job_id": job.id,
            "source": linked_application.source_type,
            "workflow_mode": locked_analysis.workflow_mode,
            "match_score": locked_analysis.match_score,
            "validation_warnings_count": len(report.validation_warnings),
            "validation_status": report.validation_status.value,
        },
    )
    if analysis_usage is not None:
        locked_usage = UsageEventRepository(db).get_for_update(
            analysis_usage.id,
            user_id=current_user.id,
        )
        if locked_usage is None:
            raise RuntimeError("Analysis usage reservation disappeared during finalization")
        stage_analysis_usage_finalization(
            db,
            locked_usage,
            user_id=current_user.id,
            analysis_id=locked_analysis.id,
            report_id=locked_analysis.id,
            workflow_mode=locked_analysis.workflow_mode,
        )

    db.add(locked_analysis)
    db.commit()
    db.refresh(locked_analysis)
    return locked_analysis


def require_active_analysis_workflow_lease(
    db: Session,
    *,
    workflow_job_id: str | None,
    user_id: int,
    lease_owner: str | None,
) -> None:
    if workflow_job_id is None:
        if lease_owner is not None:
            raise RuntimeError("A workflow lease owner was supplied without a workflow job")
        return
    if not lease_owner:
        raise RuntimeError("An active workflow lease is required for analysis finalization")
    workflow_job = WorkflowJobRepository(db).get_any_for_update(workflow_job_id)
    if (
        workflow_job is None
        or workflow_job.user_id != user_id
        or workflow_job.status != "running"
        or workflow_job.lease_owner != lease_owner
        or workflow_job.cancel_requested_at is not None
    ):
        raise RuntimeError("The analysis workflow lease is no longer active")


def _validate_finalization_context(
    *,
    report: ApplicationReport,
    current_user: CurrentUser,
    resume: ResumeRecord,
    job: JobRecord,
    analysis: AnalysisRecord,
    application: ApplicationRecord | None,
    analysis_usage: UsageEventRecord | None,
) -> None:
    if resume.user_id != current_user.id or job.user_id != current_user.id:
        raise RuntimeError("Analysis dependencies do not belong to the current user")
    if analysis.resume_id != resume.id or analysis.job_id != job.id:
        raise RuntimeError("Analysis dependencies do not match the finalized analysis")
    if (report.analysis_id, report.resume_id, report.job_id) != (
        analysis.id,
        resume.id,
        job.id,
    ):
        raise RuntimeError("Analysis report identifiers do not match persisted dependencies")
    if application is not None and application.user_id != current_user.id:
        raise RuntimeError("Application does not belong to the finalized analysis user")
    if analysis_usage is not None and analysis_usage.user_id != current_user.id:
        raise RuntimeError("Usage reservation does not belong to the finalized analysis user")
    if (
        analysis.workflow_job_id is not None
        and analysis_usage is not None
        and analysis_usage.reservation_key != analysis.workflow_job_id
    ):
        raise RuntimeError("Usage reservation does not match the analysis workflow job")


def _complete_or_validate_analysis(
    analysis: AnalysisRecord,
    *,
    workflow_result: AgentWorkflowResult | None,
) -> ApplicationReport:
    if workflow_result is None:
        if analysis.status != "completed":
            raise RuntimeError("Only completed analyses can be repaired without a workflow result")
        return ApplicationReport.model_validate(analysis.report_json)

    report = workflow_result.report
    analysis.status = "completed"
    analysis.report_json = report.model_dump(mode="json")
    analysis.report_markdown = report_to_markdown(report)
    analysis.validation_warnings_json = [
        warning.model_dump(mode="json") for warning in report.validation_warnings
    ]
    analysis.workflow_mode = workflow_result.trace.mode.value
    analysis.workflow_trace_json = workflow_result.trace.model_dump(mode="json")
    return report

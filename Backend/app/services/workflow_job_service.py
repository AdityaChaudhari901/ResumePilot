from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    AnalysisRecord,
    ApplicationRecord,
    TailoredResumeDraftRecord,
    UsageEventRecord,
    UserRecord,
    WorkflowJobRecord,
)
from app.repositories.workflow_jobs import WorkflowJobRepository
from app.schemas.agent import (
    AgentWorkflowMode,
    AgentWorkflowResult,
    AgentWorkflowTrace,
)
from app.schemas.application import ApplicationStatus
from app.schemas.auth import CurrentUser
from app.schemas.job import JobAnalysisRequest, JobProfile
from app.schemas.match import MatchResult, ScoringVersion
from app.schemas.operation import (
    ACTIVE_WORKFLOW_JOB_STATUSES,
    TERMINAL_WORKFLOW_JOB_STATUSES,
    WorkflowApproval,
    WorkflowApprovalDecision,
    WorkflowApprovalDecisionRequest,
    WorkflowApprovalStatus,
    WorkflowJobError,
    WorkflowJobKind,
    WorkflowJobListResponse,
    WorkflowJobResponse,
    WorkflowJobStatus,
)
from app.schemas.report import ApplicationReport
from app.schemas.resume import ResumeProfile
from app.schemas.tailored_resume import TailoredResumeDraftStatus
from app.schemas.usage import UsageEventState
from app.services.agent_workflow import (
    apply_approved_live_draft,
    with_langgraph_fallback_warning,
    with_live_ai_limit_warning,
    with_rejected_live_draft,
)
from app.services.analysis_service import analyze_job
from app.services.audit_service import add_audit_event
from app.services.langgraph_checkpointer import (
    delete_workflow_checkpoint,
    open_workflow_checkpointer,
)
from app.services.langgraph_workflow import LiveDraftGraphRunner
from app.services.matcher import CURRENT_SCORING_VERSION
from app.services.provider_pricing import estimate_provider_cost
from app.services.report_generator import report_to_markdown
from app.services.score_contract_service import (
    ScoreContractInvariantError,
    executable_scoring_version,
    hydrate_match_score_contract,
    hydrate_report_score_contract,
    persisted_report_payload,
    score_contract_from_analysis,
    validate_report_score_contract,
)
from app.services.tailored_resume_service import (
    draft_export_revision,
    render_tailored_resume_pdf_for_application,
    tailored_resume_export_revision,
)
from app.services.usage_service import (
    add_analysis_usage_reservation,
    add_export_usage_reservation,
    finalize_live_ai_usage,
    is_live_ai_enabled,
    release_usage_reservation,
    reserve_live_ai_usage,
    scrub_live_ai_usage_for_privacy,
)

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[\x21-\x7E]{8,255}$")
LOGGER = logging.getLogger("resumepilot.workflow_jobs")


class _CooperativeCancellation(Exception):
    pass


@dataclass(frozen=True, slots=True)
class _JobExecutionResult:
    result: dict[str, Any]
    analysis_id: int | None
    waiting_for_approval: bool = False


def enqueue_analysis_job(
    db: Session,
    request: JobAnalysisRequest,
    current_user: CurrentUser,
    *,
    idempotency_key: str,
    request_id: str | None = None,
    max_attempts: int = 3,
) -> tuple[WorkflowJobRecord, bool]:
    _validate_idempotency_key(idempotency_key)
    kind = WorkflowJobKind.analysis.value
    key_hash = _sha256(idempotency_key)
    payload = request.model_dump(mode="json", exclude_none=True)
    fingerprint = _request_fingerprint(payload)
    repository = WorkflowJobRepository(db)
    existing = repository.get_by_idempotency_key(
        user_id=current_user.id,
        kind=kind,
        idempotency_key_hash=key_hash,
    )
    if existing:
        return _validate_idempotent_replay(existing, fingerprint), False

    if request.application_id is not None:
        active = repository.list_active(
            user_id=current_user.id,
            kind=kind,
            application_id=request.application_id,
            limit=1,
        )
        if active:
            raise _active_analysis_conflict(active[0])

    job_id = str(uuid4())
    usage = add_analysis_usage_reservation(
        db,
        current_user,
        reservation_key=job_id,
    )
    existing = repository.get_by_idempotency_key(
        user_id=current_user.id,
        kind=kind,
        idempotency_key_hash=key_hash,
    )
    if existing:
        db.rollback()
        return _validate_idempotent_replay(existing, fingerprint), False

    now = datetime.now(UTC)
    record = WorkflowJobRecord(
        id=job_id,
        user_id=current_user.id,
        kind=kind,
        status=WorkflowJobStatus.queued.value,
        idempotency_key_hash=key_hash,
        request_fingerprint=fingerprint,
        payload_json=payload,
        scoring_version=CURRENT_SCORING_VERSION.value,
        stage="queued",
        progress_percent=0,
        attempt_count=0,
        max_attempts=max_attempts,
        priority=0,
        available_at=now,
        usage_event_id=usage.id,
        application_id=request.application_id,
        result_json={},
        request_id=request_id,
        created_at=now,
        updated_at=now,
    )
    try:
        repository.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        existing = repository.get_by_idempotency_key(
            user_id=current_user.id,
            kind=kind,
            idempotency_key_hash=key_hash,
        )
        if existing is not None:
            return _validate_idempotent_replay(existing, fingerprint), False
        if request.application_id is not None:
            active = repository.list_active(
                user_id=current_user.id,
                kind=kind,
                application_id=request.application_id,
                limit=1,
            )
            if active:
                raise _active_analysis_conflict(active[0]) from None
        raise
    return record, True


def enqueue_pdf_export_job(
    db: Session,
    application_id: int,
    current_user: CurrentUser,
    *,
    idempotency_key: str,
    request_id: str | None = None,
    max_attempts: int = 2,
) -> tuple[WorkflowJobRecord, bool]:
    _validate_idempotency_key(idempotency_key)
    export_revision = tailored_resume_export_revision(db, application_id, current_user)
    kind = WorkflowJobKind.pdf_export.value
    key_hash = _sha256(idempotency_key)
    payload = {
        "application_id": application_id,
        "report_id": export_revision.report_id,
        "draft_revision": export_revision.revision,
    }
    fingerprint = _request_fingerprint(payload)
    repository = WorkflowJobRepository(db)
    existing = repository.get_by_idempotency_key(
        user_id=current_user.id,
        kind=kind,
        idempotency_key_hash=key_hash,
    )
    if existing:
        return _validate_idempotent_replay(existing, fingerprint), False

    job_id = str(uuid4())
    usage = add_export_usage_reservation(
        db,
        current_user,
        report_id=export_revision.report_id,
        export_format="pdf",
        reservation_key=job_id,
    )
    existing = repository.get_by_idempotency_key(
        user_id=current_user.id,
        kind=kind,
        idempotency_key_hash=key_hash,
    )
    if existing:
        db.rollback()
        return _validate_idempotent_replay(existing, fingerprint), False

    now = datetime.now(UTC)
    record = WorkflowJobRecord(
        id=job_id,
        user_id=current_user.id,
        kind=kind,
        status=WorkflowJobStatus.queued.value,
        idempotency_key_hash=key_hash,
        request_fingerprint=fingerprint,
        payload_json=payload,
        stage="queued",
        progress_percent=0,
        attempt_count=0,
        max_attempts=max_attempts,
        priority=0,
        available_at=now,
        usage_event_id=usage.id,
        application_id=application_id,
        result_json={},
        request_id=request_id,
        created_at=now,
        updated_at=now,
    )
    try:
        repository.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        existing = repository.get_by_idempotency_key(
            user_id=current_user.id,
            kind=kind,
            idempotency_key_hash=key_hash,
        )
        if existing is None:
            raise
        return _validate_idempotent_replay(existing, fingerprint), False
    return record, True


def get_workflow_job(
    db: Session,
    job_id: str,
    current_user: CurrentUser,
) -> WorkflowJobResponse:
    record = WorkflowJobRepository(db).get(job_id, user_id=current_user.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")
    return workflow_job_response(record)


def get_workflow_job_artifact(
    db: Session,
    job_id: str,
    current_user: CurrentUser,
    *,
    settings: Settings,
) -> tuple[Path, str, str]:
    record = WorkflowJobRepository(db).get(job_id, user_id=current_user.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artifact not found")
    if (
        record.kind != WorkflowJobKind.pdf_export.value
        or record.status != WorkflowJobStatus.succeeded.value
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="PDF export is not ready for download.",
        )
    artifact = (record.result_json or {}).get("artifact")
    if not isinstance(artifact, dict):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="PDF export artifact is no longer available.",
        )
    path = _artifact_path(settings, record)
    if not path.is_file() or _file_sha256(path) != artifact.get("sha256"):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="PDF export artifact is no longer available.",
        )
    return path, str(artifact["filename"]), "application/pdf"


def list_workflow_jobs(
    db: Session,
    current_user: CurrentUser,
    *,
    limit: int,
) -> WorkflowJobListResponse:
    records = WorkflowJobRepository(db).list_recent(user_id=current_user.id, limit=limit)
    return WorkflowJobListResponse(
        items=[workflow_job_response(record) for record in records],
        count=len(records),
    )


def list_active_workflow_jobs(
    db: Session,
    current_user: CurrentUser,
    *,
    kind: WorkflowJobKind,
    application_id: int | None,
) -> WorkflowJobListResponse:
    records = WorkflowJobRepository(db).list_active(
        user_id=current_user.id,
        kind=kind.value,
        application_id=application_id,
        limit=2,
    )
    if len(records) > 1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "multiple_active_operations",
                "message": (
                    "Multiple active operations match this recovery request. "
                    "Open the relevant application before continuing."
                ),
                "operation_ids": [record.id for record in records],
            },
        )
    return WorkflowJobListResponse(
        items=[workflow_job_response(record) for record in records],
        count=len(records),
    )


def cancel_workflow_job(
    db: Session,
    job_id: str,
    current_user: CurrentUser,
    *,
    settings: Settings | None = None,
) -> WorkflowJobResponse:
    repository = WorkflowJobRepository(db)
    record = repository.get_for_update(job_id, user_id=current_user.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")
    current_status = WorkflowJobStatus(record.status)
    if current_status in TERMINAL_WORKFLOW_JOB_STATUSES:
        return workflow_job_response(record)

    now = datetime.now(UTC)
    record.cancel_requested_at = now
    if current_status in {
        WorkflowJobStatus.queued,
        WorkflowJobStatus.retry_scheduled,
        WorkflowJobStatus.waiting_for_approval,
    }:
        record.status = WorkflowJobStatus.canceled.value
        record.stage = "canceled"
        record.progress_percent = 100
        record.finished_at = now
        _release_usage_without_commit(db, record, runtime_status="canceled")
    else:
        record.status = WorkflowJobStatus.cancel_requested.value
        record.stage = "cancel_requested"
    record.updated_at = now
    saved = repository.save(record)
    if (
        saved.status == WorkflowJobStatus.canceled.value
        and saved.kind == WorkflowJobKind.analysis.value
        and settings is not None
    ):
        _delete_checkpoint_safely(settings, saved.id)
    return workflow_job_response(saved)


def submit_workflow_approval(
    db: Session,
    job_id: str,
    request: WorkflowApprovalDecisionRequest,
    current_user: CurrentUser,
    *,
    idempotency_key: str,
    settings: Settings,
) -> WorkflowJobRecord:
    """Persist an idempotent tenant-owned decision and requeue the paused graph."""

    _validate_idempotency_key(idempotency_key)
    repository = WorkflowJobRepository(db)
    record = repository.get_for_update(job_id, user_id=current_user.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")
    if record.kind != WorkflowJobKind.analysis.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This operation does not support human approval.",
        )

    approval = _approval_payload(record)
    if approval is None or approval.get("id") != request.approval_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "stale_approval",
                "message": "This approval no longer matches the pending live draft.",
            },
        )
    existing_decision = approval.get("decision")
    if existing_decision is not None:
        if existing_decision != request.decision.value:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "approval_already_decided",
                    "message": "This live draft already has a different decision.",
                },
            )
        db.rollback()
        existing = repository.get(job_id, user_id=current_user.id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")
        return existing
    if record.status != WorkflowJobStatus.waiting_for_approval.value:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The operation is not waiting for approval.",
        )

    now = datetime.now(UTC)
    approval["status"] = WorkflowApprovalStatus.submitted.value
    approval["decision"] = request.decision.value
    approval["decided_at"] = now.isoformat()
    approval["decision_key_hash"] = _sha256(idempotency_key)
    record.result_json = {**(record.result_json or {}), "_approval": approval}
    record.status = WorkflowJobStatus.queued.value
    record.stage = "approval_submitted"
    record.progress_percent = max(record.progress_percent, 90)
    record.attempt_count = 0
    record.available_at = now
    record.lease_owner = None
    record.lease_expires_at = None
    record.heartbeat_at = None
    record.error_code = None
    record.error_message = None
    record.updated_at = now
    add_audit_event(
        db,
        event_type="workflow.approval_submitted",
        user_id=current_user.id,
        request_id=record.request_id,
        payload={
            "operation_id": record.id,
            "analysis_id": record.analysis_id,
            "decision": request.decision.value,
            "approval_id": request.approval_id,
        },
    )
    saved = repository.save(record)
    if settings.execute_workflow_jobs_inline:
        return execute_workflow_job(
            db,
            saved.id,
            settings=settings,
            worker_id=f"inline-approval-{saved.id}",
        )
    return saved


def execute_workflow_job(
    db: Session,
    job_id: str,
    *,
    settings: Settings,
    worker_id: str,
) -> WorkflowJobRecord:
    repository = WorkflowJobRepository(db)
    lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.workflow_job_lease_seconds)
    record = repository.claim_by_id(
        job_id,
        worker_id=worker_id,
        lease_expires_at=lease_expires_at,
    )
    if record is None:
        existing = repository.get_any(job_id)
        if existing is None:
            raise LookupError(f"Workflow job {job_id} does not exist")
        return existing
    return _execute_claimed_job(db, record, settings=settings)


def execute_next_workflow_job(
    db: Session,
    *,
    settings: Settings,
    worker_id: str,
) -> WorkflowJobRecord | None:
    repository = WorkflowJobRepository(db)
    lease_expires_at = datetime.now(UTC) + timedelta(seconds=settings.workflow_job_lease_seconds)
    record = repository.claim_next(worker_id=worker_id, lease_expires_at=lease_expires_at)
    if record is None:
        return None
    return _execute_claimed_job(db, record, settings=settings)


def workflow_job_response(record: WorkflowJobRecord) -> WorkflowJobResponse:
    job_status = WorkflowJobStatus(record.status)
    result = dict(record.result_json or {})
    approval_payload = result.pop("_approval", None)
    approval = _public_approval(approval_payload)
    application_id = record.application_id
    if (
        isinstance(application_id, bool)
        or not isinstance(application_id, int)
        or application_id < 1
    ):
        application_id = None
    error = None
    if record.error_code and record.error_message:
        error = WorkflowJobError(code=record.error_code, message=record.error_message)
    return WorkflowJobResponse(
        id=record.id,
        application_id=application_id,
        kind=WorkflowJobKind(record.kind),
        status=job_status,
        stage=record.stage,
        progress_percent=record.progress_percent,
        attempt_count=record.attempt_count,
        max_attempts=record.max_attempts,
        cancelable=job_status in ACTIVE_WORKFLOW_JOB_STATUSES,
        result=result or None,
        approval=approval,
        error=error,
        created_at=record.created_at,
        updated_at=record.updated_at,
        started_at=record.started_at,
        finished_at=record.finished_at,
    )


def _execute_claimed_job(
    db: Session,
    record: WorkflowJobRecord,
    *,
    settings: Settings,
) -> WorkflowJobRecord:
    repository = WorkflowJobRepository(db)
    claimed_lease_owner = record.lease_owner
    try:
        if record.cancel_requested_at is not None:
            return _mark_canceled(db, record, settings=settings)
        if record.attempt_count > record.max_attempts:
            return _mark_failed(
                db,
                repository,
                record,
                RuntimeError("The workflow lease expired after the maximum attempts."),
                dead_lettered=True,
                settings=settings,
            )
        current_user = _current_user_for_job(db, record.user_id)
        with _maintain_workflow_lease(db, record, settings=settings):
            if record.kind == WorkflowJobKind.analysis.value:
                execution = _execute_analysis_job(
                    db,
                    record,
                    current_user=current_user,
                    settings=settings,
                )
            elif record.kind == WorkflowJobKind.pdf_export.value:
                execution = _JobExecutionResult(
                    result=_execute_pdf_export_job(
                        db,
                        record,
                        current_user=current_user,
                        settings=settings,
                    ),
                    analysis_id=None,
                )
            else:
                raise RuntimeError("Unsupported workflow job kind")
        db.expire_all()
        persisted = repository.get_any_for_update(record.id)
        if persisted is None:
            _delete_checkpoint_safely(settings, record.id)
            return record
        record = persisted
        if not _claimed_lease_is_current(record, claimed_lease_owner):
            db.rollback()
            return repository.get_any(record.id) or record
        if record.cancel_requested_at is not None:
            db.rollback()
            record = repository.get_any(record.id) or record
            return _mark_canceled(db, record, settings=settings)
        if execution.waiting_for_approval:
            return _mark_waiting_for_approval(
                repository,
                record,
                result=execution.result,
                analysis_id=execution.analysis_id,
            )
        now = datetime.now(UTC)
        record.status = WorkflowJobStatus.succeeded.value
        record.stage = "completed"
        record.progress_percent = 100
        record.analysis_id = execution.analysis_id
        record.result_json = execution.result
        record.error_code = None
        record.error_message = None
        record.lease_owner = None
        record.lease_expires_at = None
        record.finished_at = now
        record.updated_at = now
        saved = repository.save(record)
        if saved.kind == WorkflowJobKind.analysis.value:
            _delete_checkpoint_safely(settings, saved.id)
        return saved
    except _CooperativeCancellation:
        db.rollback()
        persisted = repository.get_any_for_update(record.id)
        if persisted is None:
            _delete_checkpoint_safely(settings, record.id)
            return record
        if not _claimed_lease_is_current(persisted, claimed_lease_owner):
            db.rollback()
            return repository.get_any(record.id) or persisted
        return _mark_canceled(db, persisted, settings=settings)
    except Exception as exc:
        db.rollback()
        persisted = repository.get_any_for_update(record.id)
        if persisted is None:
            _delete_checkpoint_safely(settings, record.id)
            return record
        if not _claimed_lease_is_current(persisted, claimed_lease_owner):
            db.rollback()
            return repository.get_any(record.id) or persisted
        record = persisted
        if record.cancel_requested_at is not None:
            return _mark_canceled(db, record, settings=settings)
        retryable = _is_retryable(exc)
        if retryable and record.attempt_count < record.max_attempts:
            return _schedule_retry(repository, record, exc)
        return _mark_failed(
            db,
            repository,
            record,
            exc,
            dead_lettered=retryable,
            settings=settings,
        )


def _claimed_lease_is_current(
    record: WorkflowJobRecord,
    expected_lease_owner: str | None,
) -> bool:
    return bool(expected_lease_owner) and record.lease_owner == expected_lease_owner


def _execute_analysis_job(
    db: Session,
    record: WorkflowJobRecord,
    *,
    current_user: CurrentUser,
    settings: Settings,
) -> _JobExecutionResult:
    lease_owner = record.lease_owner
    if not lease_owner:
        raise RuntimeError("Claimed analysis workflow is missing its lease owner")
    request = JobAnalysisRequest.model_validate(record.payload_json)
    approval_payload = _approval_payload(record)
    if (
        approval_payload
        and approval_payload.get("status") == WorkflowApprovalStatus.submitted.value
    ):
        return _resume_live_draft_workflow(
            db,
            record,
            current_user=current_user,
            settings=settings,
            approval_payload=approval_payload,
        )

    usage = _usage_reservation(db, record)
    response = analyze_job(
        db,
        request,
        current_user,
        settings,
        analysis_usage=usage,
        workflow_job_id=record.id,
        workflow_lease_owner=lease_owner,
        scoring_version=_workflow_scoring_version(record),
        release_usage_on_failure=False,
        progress_callback=lambda stage, progress: _update_progress(
            db,
            record.id,
            stage=stage,
            progress=progress,
            lease_owner=lease_owner,
        ),
    )
    baseline_result = response.model_dump(mode="json")
    if not _live_draft_requested(request, current_user=current_user, settings=settings):
        return _JobExecutionResult(result=baseline_result, analysis_id=response.analysis_id)

    analysis, deterministic_result, resume, job, match = _live_draft_context(
        db,
        response.analysis_id,
        user_id=current_user.id,
        expected_scoring_version=_workflow_scoring_version(record),
    )
    try:
        live_usage = reserve_live_ai_usage(db, current_user, operation_id=record.id)
    except HTTPException as exc:
        if exc.status_code != status.HTTP_402_PAYMENT_REQUIRED:
            raise
        limited = with_live_ai_limit_warning(deterministic_result, settings=settings)
        add_audit_event(
            db,
            event_type="workflow.live_ai_skipped_limit",
            user_id=current_user.id,
            request_id=record.request_id,
            payload={"operation_id": record.id, "analysis_id": analysis.id},
        )
        _persist_agent_result(db, analysis, limited)
        return _JobExecutionResult(result=baseline_result, analysis_id=analysis.id)
    runner = LiveDraftGraphRunner(
        settings=settings,
        resume=resume,
        job=job,
        match=match,
        deterministic_report=deterministic_result.report,
    )
    try:
        with open_workflow_checkpointer(settings) as checkpointer:
            graph_result = runner.start(
                operation_id=record.id,
                analysis_id=analysis.id,
                checkpointer=checkpointer,
            )
    except Exception as exc:
        fallback = with_langgraph_fallback_warning(
            deterministic_result,
            exc,
            settings=settings,
        )
        _persist_agent_result(db, analysis, fallback)
        release_usage_reservation(
            db,
            live_usage,
            runtime_status="fallback",
            metadata={"analysis_id": analysis.id, "operation_id": record.id},
        )
        _delete_checkpoint_safely(settings, record.id)
        return _JobExecutionResult(result=baseline_result, analysis_id=analysis.id)

    if not graph_result.paused:
        raise RuntimeError("The live-draft graph completed without requesting approval")
    cost_estimate = estimate_provider_cost(
        provider=settings.llm_provider,
        model=settings.llm_model,
        region=settings.vertex_region,
        token_usage=graph_result.sections.token_usage,
    )
    finalize_live_ai_usage(
        db,
        live_usage,
        analysis_id=analysis.id,
        runtime_status="completed",
        cost_estimate_usd=cost_estimate.amount_usd if cost_estimate else None,
    )
    approval = _new_approval_payload(graph_result)
    return _JobExecutionResult(
        result={**baseline_result, "_approval": approval},
        analysis_id=analysis.id,
        waiting_for_approval=True,
    )


def _resume_live_draft_workflow(
    db: Session,
    record: WorkflowJobRecord,
    *,
    current_user: CurrentUser,
    settings: Settings,
    approval_payload: dict[str, Any],
) -> _JobExecutionResult:
    if record.analysis_id is None:
        raise RuntimeError("The approval operation is missing its analysis")
    analysis, deterministic_result, resume, job, match = _live_draft_context(
        db,
        record.analysis_id,
        user_id=current_user.id,
        expected_scoring_version=_workflow_scoring_version(record),
    )
    decision = WorkflowApprovalDecision(str(approval_payload.get("decision")))
    proposal_revision = str(approval_payload.get("id", ""))
    runner = LiveDraftGraphRunner(
        settings=settings,
        resume=resume,
        job=job,
        match=match,
        deterministic_report=deterministic_result.report,
    )
    with open_workflow_checkpointer(settings) as checkpointer:
        graph_result = runner.resume(
            operation_id=record.id,
            decision=decision,
            proposal_revision=proposal_revision,
            checkpointer=checkpointer,
        )
    if graph_result.paused or graph_result.approval_decision != decision:
        raise RuntimeError("The live-draft graph did not apply the submitted decision")
    if graph_result.proposal_revision != proposal_revision:
        raise RuntimeError("The resumed proposal revision does not match the approved draft")

    if decision == WorkflowApprovalDecision.approve:
        final_result = apply_approved_live_draft(
            resume=resume,
            job=job,
            match=match,
            deterministic_result=deterministic_result,
            settings=settings,
            sections=graph_result.sections,
            proposal=graph_result.proposal,
            live_duration_ms=graph_result.duration_ms,
        )
        final_status = WorkflowApprovalStatus.approved
    else:
        final_result = with_rejected_live_draft(
            deterministic_result,
            settings=settings,
            sections=graph_result.sections,
            live_duration_ms=graph_result.duration_ms,
        )
        final_status = WorkflowApprovalStatus.rejected

    _persist_agent_result(db, analysis, final_result, commit=False)
    approval_payload["status"] = final_status.value
    approval_payload["decision"] = decision.value
    approval_payload.pop("decision_key_hash", None)
    approval_payload.pop("_sections", None)
    add_audit_event(
        db,
        event_type=f"workflow.live_draft_{final_status.value}",
        user_id=current_user.id,
        request_id=record.request_id,
        payload={
            "operation_id": record.id,
            "analysis_id": analysis.id,
            "approval_id": proposal_revision,
        },
    )
    return _JobExecutionResult(
        result={**_analysis_result_payload(analysis), "_approval": approval_payload},
        analysis_id=analysis.id,
    )


def _live_draft_requested(
    request: JobAnalysisRequest,
    *,
    current_user: CurrentUser,
    settings: Settings,
) -> bool:
    return (
        settings.agent_workflow_mode == AgentWorkflowMode.langgraph
        and request.allow_live_ai_processing
        and is_live_ai_enabled(current_user)
    )


def _live_draft_context(
    db: Session,
    analysis_id: int,
    *,
    user_id: int,
    expected_scoring_version: ScoringVersion,
) -> tuple[AnalysisRecord, AgentWorkflowResult, ResumeProfile, JobProfile, MatchResult]:
    analysis = db.scalar(
        select(AnalysisRecord)
        .where(AnalysisRecord.id == analysis_id, AnalysisRecord.user_id == user_id)
        .limit(1)
    )
    if analysis is None:
        raise RuntimeError("The analysis for this workflow no longer exists")
    resume = ResumeProfile.model_validate(analysis.resume.profile_json)
    job = JobProfile.model_validate(analysis.job.profile_json)
    match = hydrate_match_score_contract(
        analysis,
        MatchResult.model_validate(analysis.match_result_json),
    )
    if executable_scoring_version(match.scoring_version) != expected_scoring_version:
        raise ScoreContractInvariantError(
            "Analysis scorer does not match the approval workflow snapshot"
        )
    deterministic_result = AgentWorkflowResult(
        report=hydrate_report_score_contract(
            analysis,
            ApplicationReport.model_validate(analysis.report_json),
        ),
        trace=AgentWorkflowTrace.model_validate(analysis.workflow_trace_json),
    )
    return analysis, deterministic_result, resume, job, match


def _persist_agent_result(
    db: Session,
    analysis: AnalysisRecord,
    result: AgentWorkflowResult,
    *,
    commit: bool = True,
) -> None:
    validate_report_score_contract(analysis, result.report)
    analysis.status = "completed"
    analysis.report_json = persisted_report_payload(result.report)
    analysis.report_markdown = report_to_markdown(result.report)
    analysis.validation_warnings_json = [
        warning.model_dump(mode="json") for warning in result.report.validation_warnings
    ]
    analysis.workflow_mode = result.trace.mode.value
    analysis.workflow_trace_json = result.trace.model_dump(mode="json")
    db.add(analysis)
    if commit:
        db.commit()
        db.refresh(analysis)


def _analysis_result_payload(analysis: AnalysisRecord) -> dict[str, Any]:
    scoring_version, score_status, _breakdown = score_contract_from_analysis(analysis)
    return {
        "analysis_id": analysis.id,
        "report_id": analysis.id,
        "match_score": analysis.match_score,
        "scoring_version": scoring_version.value,
        "score_status": score_status.value,
        "status": analysis.status,
    }


def _workflow_scoring_version(record: WorkflowJobRecord) -> ScoringVersion:
    return executable_scoring_version(record.scoring_version)


def _new_approval_payload(graph_result: Any) -> dict[str, Any]:
    return {
        "id": graph_result.proposal_revision,
        "kind": "live_ai_draft",
        "status": WorkflowApprovalStatus.pending.value,
        "title": "Review the validated live draft",
        "message": (
            "Approve only the safe live wording shown here, or keep the deterministic report. "
            "This decision does not accept tailored resume bullets or unlock exports."
        ),
        "warning_codes": graph_result.validation_warning_codes,
        "requested_at": graph_result.requested_at.isoformat(),
        "decision": None,
        "decided_at": None,
        "proposal": graph_result.proposal.model_dump(mode="json"),
        "_sections": graph_result.sections.model_dump(mode="json"),
    }


def _approval_payload(record: WorkflowJobRecord) -> dict[str, Any] | None:
    value = (record.result_json or {}).get("_approval")
    return dict(value) if isinstance(value, dict) else None


def _public_approval(value: Any) -> WorkflowApproval | None:
    if not isinstance(value, dict):
        return None
    public_keys = WorkflowApproval.model_fields.keys()
    return WorkflowApproval.model_validate({key: value.get(key) for key in public_keys})


def _execute_pdf_export_job(
    db: Session,
    record: WorkflowJobRecord,
    *,
    current_user: CurrentUser,
    settings: Settings,
) -> dict[str, Any]:
    application_id = int(record.payload_json["application_id"])
    expected_report_id = int(record.payload_json["report_id"])
    expected_revision = str(record.payload_json["draft_revision"])
    revision = tailored_resume_export_revision(db, application_id, current_user)
    if revision.report_id != expected_report_id or revision.revision != expected_revision:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The accepted tailored resume changed. Start a new PDF export.",
        )

    _update_progress(
        db,
        record.id,
        stage="compiling_pdf",
        progress=45,
        lease_owner=record.lease_owner,
    )
    rendered = render_tailored_resume_pdf_for_application(
        db,
        application_id,
        settings,
        current_user,
    )
    db.expire_all()
    current_job = WorkflowJobRepository(db).get_any(record.id)
    if current_job is None or current_job.cancel_requested_at is not None:
        raise _CooperativeCancellation

    _update_progress(
        db,
        record.id,
        stage="saving_pdf",
        progress=80,
        lease_owner=record.lease_owner,
    )

    current_job = db.scalar(
        select(WorkflowJobRecord).where(WorkflowJobRecord.id == record.id).with_for_update()
    )
    if current_job is None or current_job.cancel_requested_at is not None:
        raise _CooperativeCancellation

    application = db.scalar(
        select(ApplicationRecord)
        .where(
            ApplicationRecord.id == application_id,
            ApplicationRecord.user_id == current_user.id,
        )
        .with_for_update()
    )
    draft = db.scalar(
        select(TailoredResumeDraftRecord)
        .where(
            TailoredResumeDraftRecord.application_id == application_id,
            TailoredResumeDraftRecord.user_id == current_user.id,
        )
        .with_for_update()
    )
    if (
        application is None
        or draft is None
        or application.report_id != expected_report_id
        or draft.report_id != expected_report_id
        or draft_export_revision(draft) != expected_revision
        or rendered.report_id != expected_report_id
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The accepted tailored resume changed while PDF export was running.",
        )

    pdf = bytes(rendered.content)
    path = _persist_pdf_artifact(settings, record, pdf)
    usage = _usage_reservation(db, record)
    now = datetime.now(UTC)
    usage.state = UsageEventState.consumed.value
    usage.settled_at = now
    usage.metadata_json = {
        "status": "completed",
        "application_id": application_id,
        "report_id": expected_report_id,
        "format": "pdf",
        "operation_id": record.id,
    }
    draft.status = TailoredResumeDraftStatus.exported.value
    if application.status != ApplicationStatus.applied.value:
        application.status = ApplicationStatus.exported.value
    add_audit_event(
        db,
        event_type="tailored_resume.exported",
        user_id=current_user.id,
        request_id=record.request_id,
        payload={
            "application_id": application_id,
            "report_id": expected_report_id,
            "format": "pdf",
            "operation_id": record.id,
        },
    )
    db.add(usage)
    db.add(draft)
    db.add(application)
    db.commit()
    filename = f"resumepilot-application-{application_id}.pdf"
    return {
        "application_id": application_id,
        "report_id": expected_report_id,
        "artifact": {
            "download_url": f"/operations/{record.id}/artifact",
            "filename": filename,
            "media_type": "application/pdf",
            "size_bytes": len(pdf),
            "sha256": _file_sha256(path),
        },
    }


def _artifact_path(settings: Settings, record: WorkflowJobRecord) -> Path:
    return settings.export_dir / str(record.user_id) / f"{record.id}.pdf"


def _persist_pdf_artifact(
    settings: Settings,
    record: WorkflowJobRecord,
    content: bytes,
) -> Path:
    destination = _artifact_path(settings, record)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            dir=destination.parent,
            prefix=f".{record.id}-",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary.write(content)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)
        os.chmod(temporary_path, 0o600)
        os.replace(temporary_path, destination)
        return destination
    finally:
        if temporary_path and temporary_path.exists():
            temporary_path.unlink()


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _update_progress(
    db: Session,
    job_id: str,
    *,
    stage: str,
    progress: int,
    lease_owner: str | None,
) -> None:
    if not lease_owner:
        return
    heartbeat_at = datetime.now(UTC)
    progress_value = min(progress, 95)
    db.execute(
        update(WorkflowJobRecord)
        .where(
            WorkflowJobRecord.id == job_id,
            WorkflowJobRecord.status == WorkflowJobStatus.running.value,
            WorkflowJobRecord.lease_owner == lease_owner,
        )
        .values(
            stage=stage[:64],
            progress_percent=case(
                (WorkflowJobRecord.progress_percent < progress_value, progress_value),
                else_=WorkflowJobRecord.progress_percent,
            ),
            heartbeat_at=heartbeat_at,
            updated_at=heartbeat_at,
        )
    )
    db.commit()


@contextmanager
def _maintain_workflow_lease(
    db: Session,
    record: WorkflowJobRecord,
    *,
    settings: Settings,
):
    """Renew a claimed job lease while one potentially slow stage is running."""

    if not record.lease_owner:
        yield
        return

    stop = Event()
    interval_seconds = max(5.0, min(settings.workflow_job_lease_seconds / 3, 60.0))
    bind = db.get_bind()
    record_id = record.id
    lease_owner = record.lease_owner

    def heartbeat() -> None:
        while not stop.wait(interval_seconds):
            now = datetime.now(UTC)
            try:
                with Session(bind=bind) as heartbeat_db:
                    renewed = _renew_workflow_lease(
                        heartbeat_db,
                        record_id=record_id,
                        lease_owner=lease_owner,
                        lease_seconds=settings.workflow_job_lease_seconds,
                        now=now,
                    )
                    if not renewed:
                        return
            except Exception:
                LOGGER.exception(
                    "workflow job heartbeat failed",
                    extra={"workflow_job_id": record_id},
                )
                return

    thread = Thread(
        target=heartbeat,
        name=f"workflow-heartbeat-{record_id[:8]}",
        daemon=True,
    )
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=interval_seconds + 1)


def _renew_workflow_lease(
    db: Session,
    *,
    record_id: str,
    lease_owner: str,
    lease_seconds: int,
    now: datetime | None = None,
) -> bool:
    heartbeat_at = now or datetime.now(UTC)
    renewed = db.execute(
        update(WorkflowJobRecord)
        .where(
            WorkflowJobRecord.id == record_id,
            WorkflowJobRecord.status == WorkflowJobStatus.running.value,
            WorkflowJobRecord.lease_owner == lease_owner,
        )
        .values(
            heartbeat_at=heartbeat_at,
            lease_expires_at=heartbeat_at + timedelta(seconds=lease_seconds),
            updated_at=heartbeat_at,
        )
    )
    db.commit()
    return renewed.rowcount == 1


def _mark_waiting_for_approval(
    repository: WorkflowJobRepository,
    record: WorkflowJobRecord,
    *,
    result: dict[str, Any],
    analysis_id: int | None,
) -> WorkflowJobRecord:
    now = datetime.now(UTC)
    record.status = WorkflowJobStatus.waiting_for_approval.value
    record.stage = "approval_required"
    record.progress_percent = 90
    record.analysis_id = analysis_id
    record.result_json = result
    record.error_code = None
    record.error_message = None
    record.lease_owner = None
    record.lease_expires_at = None
    record.heartbeat_at = None
    record.finished_at = None
    record.updated_at = now
    return repository.save(record)


def _schedule_retry(
    repository: WorkflowJobRepository,
    record: WorkflowJobRecord,
    exc: Exception,
) -> WorkflowJobRecord:
    now = datetime.now(UTC)
    delay_seconds = min(2 ** max(record.attempt_count, 1), 60)
    record.status = WorkflowJobStatus.retry_scheduled.value
    record.stage = "retry_scheduled"
    record.available_at = now + timedelta(seconds=delay_seconds)
    record.error_code, record.error_message = _public_error(exc)
    record.lease_owner = None
    record.lease_expires_at = None
    record.updated_at = now
    return repository.save(record)


def _mark_failed(
    db: Session,
    repository: WorkflowJobRepository,
    record: WorkflowJobRecord,
    exc: Exception,
    *,
    dead_lettered: bool,
    settings: Settings,
) -> WorkflowJobRecord:
    now = datetime.now(UTC)
    record.status = (
        WorkflowJobStatus.dead_lettered.value if dead_lettered else WorkflowJobStatus.failed.value
    )
    record.stage = record.status
    record.progress_percent = 100
    record.error_code, record.error_message = _public_error(exc)
    record.lease_owner = None
    record.lease_expires_at = None
    record.finished_at = now
    record.updated_at = now
    _release_usage_without_commit(db, record, runtime_status=record.status)
    saved = repository.save(record)
    if saved.kind == WorkflowJobKind.analysis.value:
        _delete_checkpoint_safely(settings, saved.id)
    return saved


def _mark_canceled(
    db: Session,
    record: WorkflowJobRecord,
    *,
    settings: Settings,
) -> WorkflowJobRecord:
    now = datetime.now(UTC)
    privacy_deletion_requested = record.stage == "privacy_deletion_requested"
    record.status = WorkflowJobStatus.canceled.value
    record.stage = "canceled"
    record.progress_percent = 100
    record.lease_owner = None
    record.lease_expires_at = None
    record.finished_at = now
    record.updated_at = now
    _release_usage_without_commit(db, record, runtime_status="canceled")
    if privacy_deletion_requested:
        scrub_live_ai_usage_for_privacy(
            db,
            user_id=record.user_id,
            operation_id=record.id,
        )
    saved = WorkflowJobRepository(db).save(record)
    if saved.kind == WorkflowJobKind.analysis.value:
        _delete_checkpoint_safely(settings, saved.id)
    return saved


def _delete_checkpoint_safely(settings: Settings | None, thread_id: str) -> None:
    if settings is None:
        return
    try:
        delete_workflow_checkpoint(settings, thread_id)
    except Exception:
        LOGGER.exception(
            "Failed to delete terminal LangGraph checkpoint",
            extra={"workflow_job_id": thread_id},
        )


def _release_usage_without_commit(
    db: Session,
    record: WorkflowJobRecord,
    *,
    runtime_status: str,
) -> None:
    usage = _usage_reservation(db, record)
    if usage.state != UsageEventState.reserved.value:
        return
    usage.state = UsageEventState.released.value
    usage.settled_at = datetime.now(UTC)
    usage.metadata_json = {"status": runtime_status, "operation_id": record.id}
    db.add(usage)


def _usage_reservation(db: Session, record: WorkflowJobRecord) -> UsageEventRecord:
    usage = db.get(UsageEventRecord, record.usage_event_id)
    if usage is None or usage.user_id != record.user_id:
        raise RuntimeError("Workflow job usage reservation is missing")
    return usage


def _current_user_for_job(db: Session, user_id: int) -> CurrentUser:
    user = db.get(UserRecord, user_id)
    if user is None:
        raise RuntimeError("Workflow job user no longer exists")
    return CurrentUser(
        id=user.id,
        external_id=user.external_id,
        email=user.email,
        display_name=user.display_name,
        plan=user.plan,
        subscription_status=user.subscription_status,
    )


def _validate_idempotency_key(value: str) -> None:
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Idempotency-Key must contain 8-255 visible ASCII characters and must be "
                "reused only for the same request."
            ),
        )


def _validate_idempotent_replay(
    record: WorkflowJobRecord,
    fingerprint: str,
) -> WorkflowJobRecord:
    if record.request_fingerprint != fingerprint:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "idempotency_key_reused",
                "message": "This Idempotency-Key was already used for a different request.",
                "operation_id": record.id,
            },
        )
    return record


def _active_analysis_conflict(record: WorkflowJobRecord) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "analysis_already_active",
            "message": "An analysis is already active for this application.",
            "operation_id": record.id,
            "application_id": record.application_id,
        },
    )


def _request_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return _sha256(canonical)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, ScoreContractInvariantError):
        return False
    if isinstance(exc, HTTPException):
        return exc.status_code in {408, 425, 429, 500, 502, 503, 504}
    return not isinstance(exc, (ValueError, TypeError))


def _public_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, ScoreContractInvariantError):
        return "score_contract_invalid", "Stored score provenance failed an integrity check."
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, str):
            return f"http_{exc.status_code}", exc.detail[:500]
        return f"http_{exc.status_code}", "The operation could not be completed."
    return "internal_error", "The operation failed safely. Retry or review the source input."

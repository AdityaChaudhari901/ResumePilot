from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, Thread
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import (
    ApplicationRecord,
    TailoredResumeDraftRecord,
    UsageEventRecord,
    UserRecord,
    WorkflowJobRecord,
)
from app.repositories.workflow_jobs import WorkflowJobRepository
from app.schemas.application import ApplicationStatus
from app.schemas.auth import CurrentUser
from app.schemas.job import JobAnalysisRequest
from app.schemas.operation import (
    TERMINAL_WORKFLOW_JOB_STATUSES,
    WorkflowJobError,
    WorkflowJobKind,
    WorkflowJobListResponse,
    WorkflowJobResponse,
    WorkflowJobStatus,
)
from app.schemas.tailored_resume import TailoredResumeDraftStatus
from app.schemas.usage import UsageEventState
from app.services.analysis_service import analyze_job
from app.services.audit_service import add_audit_event
from app.services.tailored_resume_service import (
    draft_export_revision,
    render_tailored_resume_pdf_for_application,
    tailored_resume_export_revision,
)
from app.services.usage_service import (
    add_analysis_usage_reservation,
    add_export_usage_reservation,
)

IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[\x21-\x7E]{8,255}$")
ACTIVE_WORKFLOW_JOB_STATUSES = frozenset(
    {
        WorkflowJobStatus.queued,
        WorkflowJobStatus.running,
        WorkflowJobStatus.retry_scheduled,
        WorkflowJobStatus.cancel_requested,
    }
)
LOGGER = logging.getLogger("resumepilot.workflow_jobs")


class _CooperativeCancellation(Exception):
    pass


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
        stage="queued",
        progress_percent=0,
        attempt_count=0,
        max_attempts=max_attempts,
        priority=0,
        available_at=now,
        usage_event_id=usage.id,
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


def cancel_workflow_job(
    db: Session,
    job_id: str,
    current_user: CurrentUser,
) -> WorkflowJobResponse:
    repository = WorkflowJobRepository(db)
    record = repository.get(job_id, user_id=current_user.id)
    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Operation not found")
    current_status = WorkflowJobStatus(record.status)
    if current_status in TERMINAL_WORKFLOW_JOB_STATUSES:
        return workflow_job_response(record)

    now = datetime.now(UTC)
    record.cancel_requested_at = now
    if current_status in {WorkflowJobStatus.queued, WorkflowJobStatus.retry_scheduled}:
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
    return workflow_job_response(saved)


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
    error = None
    if record.error_code and record.error_message:
        error = WorkflowJobError(code=record.error_code, message=record.error_message)
    return WorkflowJobResponse(
        id=record.id,
        kind=WorkflowJobKind(record.kind),
        status=job_status,
        stage=record.stage,
        progress_percent=record.progress_percent,
        attempt_count=record.attempt_count,
        max_attempts=record.max_attempts,
        cancelable=job_status in ACTIVE_WORKFLOW_JOB_STATUSES,
        result=record.result_json or None,
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
    try:
        if record.cancel_requested_at is not None:
            return _mark_canceled(db, record)
        if record.attempt_count > record.max_attempts:
            return _mark_failed(
                db,
                repository,
                record,
                RuntimeError("The workflow lease expired after the maximum attempts."),
                dead_lettered=True,
            )
        current_user = _current_user_for_job(db, record.user_id)
        with _maintain_workflow_lease(db, record, settings=settings):
            if record.kind == WorkflowJobKind.analysis.value:
                result, analysis_id = _execute_analysis_job(
                    db,
                    record,
                    current_user=current_user,
                    settings=settings,
                )
            elif record.kind == WorkflowJobKind.pdf_export.value:
                result = _execute_pdf_export_job(
                    db,
                    record,
                    current_user=current_user,
                    settings=settings,
                )
                analysis_id = None
            else:
                raise RuntimeError("Unsupported workflow job kind")
        db.expire_all()
        persisted = repository.get_any(record.id)
        if persisted is None:
            return record
        record = persisted
        if record.cancel_requested_at is not None:
            return _mark_canceled(db, record)
        now = datetime.now(UTC)
        record.status = WorkflowJobStatus.succeeded.value
        record.stage = "completed"
        record.progress_percent = 100
        record.analysis_id = analysis_id
        record.result_json = result
        record.error_code = None
        record.error_message = None
        record.lease_owner = None
        record.lease_expires_at = None
        record.finished_at = now
        record.updated_at = now
        return repository.save(record)
    except _CooperativeCancellation:
        db.rollback()
        persisted = repository.get_any(record.id)
        if persisted is None:
            return record
        return _mark_canceled(db, persisted)
    except Exception as exc:
        db.rollback()
        persisted = repository.get_any(record.id)
        if persisted is None:
            return record
        record = persisted
        if record.cancel_requested_at is not None:
            return _mark_canceled(db, record)
        retryable = _is_retryable(exc)
        if retryable and record.attempt_count < record.max_attempts:
            return _schedule_retry(repository, record, exc)
        return _mark_failed(db, repository, record, exc, dead_lettered=retryable)


def _execute_analysis_job(
    db: Session,
    record: WorkflowJobRecord,
    *,
    current_user: CurrentUser,
    settings: Settings,
) -> tuple[dict[str, Any], int]:
    request = JobAnalysisRequest.model_validate(record.payload_json)
    usage = _usage_reservation(db, record)
    response = analyze_job(
        db,
        request,
        current_user,
        settings,
        analysis_usage=usage,
        workflow_job_id=record.id,
        release_usage_on_failure=False,
        progress_callback=lambda stage, progress: _update_progress(
            db,
            record.id,
            stage=stage,
            progress=progress,
        ),
    )
    return response.model_dump(mode="json"), response.analysis_id


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

    _update_progress(db, record.id, stage="compiling_pdf", progress=45)
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

    _update_progress(db, record.id, stage="saving_pdf", progress=80)

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
) -> None:
    record = WorkflowJobRepository(db).get_any(job_id)
    if record is None or WorkflowJobStatus(record.status) != WorkflowJobStatus.running:
        return
    record.stage = stage[:64]
    record.progress_percent = max(record.progress_percent, min(progress, 95))
    record.heartbeat_at = datetime.now(UTC)
    record.updated_at = record.heartbeat_at
    db.add(record)
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
    return repository.save(record)


def _mark_canceled(db: Session, record: WorkflowJobRecord) -> WorkflowJobRecord:
    now = datetime.now(UTC)
    record.status = WorkflowJobStatus.canceled.value
    record.stage = "canceled"
    record.progress_percent = 100
    record.lease_owner = None
    record.lease_expires_at = None
    record.finished_at = now
    record.updated_at = now
    _release_usage_without_commit(db, record, runtime_status="canceled")
    return WorkflowJobRepository(db).save(record)


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


def _request_fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
    return _sha256(canonical)


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_retryable(exc: Exception) -> bool:
    if isinstance(exc, HTTPException):
        return exc.status_code in {408, 425, 429, 500, 502, 503, 504}
    return not isinstance(exc, (ValueError, TypeError))


def _public_error(exc: Exception) -> tuple[str, str]:
    if isinstance(exc, HTTPException):
        if isinstance(exc.detail, str):
            return f"http_{exc.status_code}", exc.detail[:500]
        return f"http_{exc.status_code}", "The operation could not be completed."
    return "internal_error", "The operation failed safely. Retry or review the source input."

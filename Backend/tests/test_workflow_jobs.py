from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import UsageEventRecord, WorkflowJobRecord
from app.services.workflow_job_service import (
    _renew_workflow_lease,
    execute_next_workflow_job,
    execute_workflow_job,
)
from tests.api_helpers import submit_analysis


def test_analysis_idempotency_replays_one_result_and_one_charge(
    client,
    sample_resume_text,
    sample_job_text,
):
    resume_id = _upload_resume(client, sample_resume_text)
    payload = {"resume_id": resume_id, "job_text": sample_job_text}

    first_response, first = submit_analysis(
        client,
        payload,
        idempotency_key="analysis-idempotency-replay",
    )
    second_response, second = submit_analysis(
        client,
        payload,
        idempotency_key="analysis-idempotency-replay",
    )

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert first is not None and second is not None
    assert first["id"] == second["id"]
    assert first["result"] == second["result"]
    assert client.get("/usage/summary").json()["limits"][0]["used"] == 1


def test_idempotency_key_reuse_with_different_request_is_rejected(
    client,
    sample_resume_text,
    sample_job_text,
):
    resume_id = _upload_resume(client, sample_resume_text)
    first_response, _first = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-idempotency-conflict",
    )
    conflict_response, conflict = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": f"{sample_job_text}\nDifferent request."},
        idempotency_key="analysis-idempotency-conflict",
    )

    assert first_response.status_code == 202
    assert conflict_response.status_code == 409
    assert conflict is not None
    assert conflict["detail"]["code"] == "idempotency_key_reused"


def test_queued_analysis_can_be_canceled_without_consuming_quota(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)

    response, queued = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-cancel-queued",
    )

    assert response.status_code == 202
    assert queued is not None
    assert queued["status"] == "queued"
    canceled_response = client.post(f"/operations/{queued['id']}/cancel")
    assert canceled_response.status_code == 200
    assert canceled_response.json()["status"] == "canceled"
    assert client.get("/usage/summary").json()["limits"][0]["used"] == 0


def test_old_active_reservations_still_enforce_analysis_limit(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)

    for index in range(3):
        response, queued = submit_analysis(
            client,
            {"resume_id": resume_id, "job_text": f"{sample_job_text}\nQueue marker: {index}"},
            idempotency_key=f"analysis-old-active-{index}",
        )
        assert response.status_code == 202
        assert queued is not None
        assert queued["status"] == "queued"

    with client.app.state.session_factory() as db:
        reservations = list(
            db.scalars(select(UsageEventRecord).where(UsageEventRecord.state == "reserved"))
        )
        assert len(reservations) == 3
        stale_at = datetime.now(UTC) - timedelta(seconds=settings.usage_reservation_ttl_seconds + 1)
        for reservation in reservations:
            reservation.reserved_at = stale_at
        db.commit()

    response, operation = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": f"{sample_job_text}\nQueue marker: blocked"},
        idempotency_key="analysis-old-active-blocked",
    )

    assert response.status_code == 402
    assert operation is not None
    assert operation["detail"]["code"] == "plan_limit_reached"
    assert operation["detail"]["used"] == 3


def test_worker_executes_a_queued_analysis_and_exposes_progress_result(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)
    response, queued = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-worker-once",
    )
    assert response.status_code == 202
    assert queued is not None

    with client.app.state.session_factory() as db:
        settled = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="pytest-worker",
        )

    assert settled.status == "succeeded"
    operation_response = client.get(f"/operations/{queued['id']}")
    assert operation_response.status_code == 200
    operation = operation_response.json()
    assert operation["stage"] == "completed"
    assert operation["progress_percent"] == 100
    assert operation["attempt_count"] == 1
    assert operation["result"]["status"] == "completed"


def test_worker_reaps_expired_cancel_request_without_consuming_quota(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)
    response, queued = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-cancel-stale-lease",
    )
    assert response.status_code == 202
    assert queued is not None

    with client.app.state.session_factory() as db:
        record = db.get(WorkflowJobRecord, queued["id"])
        assert record is not None
        record.status = "cancel_requested"
        record.cancel_requested_at = datetime.now(UTC)
        record.lease_owner = "crashed-worker"
        record.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

        settled = execute_next_workflow_job(
            db,
            settings=settings,
            worker_id="recovery-worker",
        )

    assert settled is not None
    assert settled.id == queued["id"]
    assert settled.status == "canceled"
    assert client.get("/usage/summary").json()["limits"][0]["used"] == 0


def test_worker_dead_letters_expired_lease_after_maximum_attempts(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)
    response, queued = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-dead-letter-stale-lease",
    )
    assert response.status_code == 202
    assert queued is not None

    with client.app.state.session_factory() as db:
        record = db.get(WorkflowJobRecord, queued["id"])
        assert record is not None
        record.status = "running"
        record.attempt_count = record.max_attempts
        record.lease_owner = "crashed-worker"
        record.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()

        settled = execute_next_workflow_job(
            db,
            settings=settings,
            worker_id="recovery-worker",
        )

    assert settled is not None
    assert settled.id == queued["id"]
    assert settled.status == "dead_lettered"
    assert settled.attempt_count == settled.max_attempts + 1
    assert client.get("/usage/summary").json()["limits"][0]["used"] == 0


def test_worker_heartbeat_renews_only_the_current_owner_lease(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)
    response, queued = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-heartbeat-owner",
    )
    assert response.status_code == 202
    assert queued is not None

    heartbeat_at = datetime.now(UTC)
    with client.app.state.session_factory() as db:
        record = db.get(WorkflowJobRecord, queued["id"])
        assert record is not None
        record.status = "running"
        record.lease_owner = "active-worker"
        record.lease_expires_at = heartbeat_at + timedelta(seconds=1)
        db.commit()

        assert not _renew_workflow_lease(
            db,
            record_id=record.id,
            lease_owner="stale-worker",
            lease_seconds=60,
            now=heartbeat_at,
        )
        assert _renew_workflow_lease(
            db,
            record_id=record.id,
            lease_owner="active-worker",
            lease_seconds=60,
            now=heartbeat_at,
        )
        db.refresh(record)

    assert record.heartbeat_at.replace(tzinfo=UTC) == heartbeat_at
    assert record.lease_expires_at.replace(tzinfo=UTC) == heartbeat_at + timedelta(seconds=60)


def _upload_resume(client, resume_text: str) -> int:
    response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 201
    return response.json()["resume_id"]

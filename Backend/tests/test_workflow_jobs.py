from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import (
    AnalysisRecord,
    ApplicationRecord,
    AuditEventRecord,
    TailoredResumeDraftRecord,
    UsageEventRecord,
    WorkflowJobRecord,
)
from app.repositories.audit_events import AuditEventRepository
from app.repositories.workflow_jobs import WorkflowJobRepository
from app.services.workflow_job_service import (
    _renew_workflow_lease,
    _update_progress,
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
        persisted = db.get(WorkflowJobRecord, queued["id"])
        assert persisted is not None
        assert persisted.scoring_version == "evidence_v2"
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
    assert operation["result"]["scoring_version"] == "evidence_v2"
    assert operation["result"]["score_status"] == "scored"


def test_worker_uses_the_scoring_version_snapshotted_at_enqueue(
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
        idempotency_key="analysis-version-snapshot",
    )
    assert response.status_code == 202
    assert queued is not None

    with client.app.state.session_factory() as db:
        record = db.get(WorkflowJobRecord, queued["id"])
        assert record is not None
        record.scoring_version = "deterministic_v1"
        db.commit()
        settled = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="versioned-worker",
        )

    assert settled.status == "succeeded"
    assert settled.result_json["scoring_version"] == "deterministic_v1"
    with client.app.state.session_factory() as db:
        analysis = db.scalar(
            select(AnalysisRecord).where(AnalysisRecord.workflow_job_id == queued["id"])
        )
        assert analysis is not None
        assert analysis.scoring_version == "deterministic_v1"
        assert analysis.score_breakdown_json is None


def test_new_worker_replays_an_old_writer_v1_analysis_with_legacy_metadata(
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
        idempotency_key="analysis-old-writer-v1-replay",
    )
    assert response.status_code == 202
    assert queued is not None

    with client.app.state.session_factory() as db:
        record = db.get(WorkflowJobRecord, queued["id"])
        assert record is not None
        record.scoring_version = "deterministic_v1"
        db.commit()
        completed = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="old-writer-worker",
        )
        assert completed.status == "succeeded"

        analysis = db.scalar(
            select(AnalysisRecord).where(AnalysisRecord.workflow_job_id == queued["id"])
        )
        assert analysis is not None
        analysis.scoring_version = "legacy_unversioned"
        completed.status = "retry_scheduled"
        completed.stage = "retry_scheduled"
        completed.available_at = datetime.now(UTC) - timedelta(seconds=1)
        completed.finished_at = None
        db.commit()

        replay = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="new-v1-compatible-worker",
        )

    assert replay.status == "succeeded"
    assert replay.result_json["scoring_version"] == "legacy_unversioned"


def test_completed_replay_rejects_analysis_version_that_differs_from_job_snapshot(
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
        idempotency_key="analysis-version-mismatch",
    )
    assert response.status_code == 202
    assert queued is not None

    with client.app.state.session_factory() as db:
        completed = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="version-baseline-worker",
        )
        assert completed.status == "succeeded"
        analysis = db.scalar(
            select(AnalysisRecord).where(AnalysisRecord.workflow_job_id == queued["id"])
        )
        assert analysis is not None
        analysis.scoring_version = "deterministic_v1"
        analysis.score_breakdown_json = None
        completed.status = "retry_scheduled"
        completed.stage = "retry_scheduled"
        completed.available_at = datetime.now(UTC) - timedelta(seconds=1)
        completed.finished_at = None
        db.commit()

        replay = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="version-mismatch-worker",
        )

    assert replay.status == "failed"
    assert replay.error_code == "score_contract_invalid"


def test_analysis_finalization_rolls_back_and_retry_converges(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)
    response, queued = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-finalization-rollback",
    )
    assert response.status_code == 202
    assert queued is not None

    original_add = AuditEventRepository.add

    def fail_job_audit(repository, record):
        if record.event_type == "job.analyzed":
            raise RuntimeError("simulated post-application finalization failure")
        return original_add(repository, record)

    monkeypatch.setattr(AuditEventRepository, "add", fail_job_audit)
    with client.app.state.session_factory() as db:
        retry = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="fault-worker",
        )

    assert retry.status == "retry_scheduled"
    with client.app.state.session_factory() as db:
        analyses = list(
            db.scalars(select(AnalysisRecord).where(AnalysisRecord.workflow_job_id == queued["id"]))
        )
        assert not any(analysis.status == "completed" for analysis in analyses)
        assert not list(
            db.scalars(select(ApplicationRecord).where(ApplicationRecord.user_id == retry.user_id))
        )
        assert _analysis_audit_counts(db, user_id=retry.user_id) == {
            "application.analyzed": 0,
            "job.analyzed": 0,
        }
        usage = db.get(UsageEventRecord, retry.usage_event_id)
        assert usage is not None
        assert usage.state == "reserved"

    monkeypatch.setattr(AuditEventRepository, "add", original_add)
    with client.app.state.session_factory() as db:
        retry = db.get(WorkflowJobRecord, queued["id"])
        assert retry is not None
        retry.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        settled = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="recovery-worker",
        )

    assert settled.status == "succeeded"
    _assert_complete_analysis_finalization(client, operation_id=queued["id"])


def test_post_finalizer_job_save_failure_replays_without_duplicate_side_effects(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)
    response, queued = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-post-finalizer-crash",
    )
    assert response.status_code == 202
    assert queued is not None

    original_save = WorkflowJobRepository.save
    failed_once = False

    def fail_first_success_save(repository, record):
        nonlocal failed_once
        if record.status == "succeeded" and not failed_once:
            failed_once = True
            raise RuntimeError("simulated crash before operation success commit")
        return original_save(repository, record)

    monkeypatch.setattr(WorkflowJobRepository, "save", fail_first_success_save)
    with client.app.state.session_factory() as db:
        retry = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="post-finalizer-fault-worker",
        )

    assert retry.status == "retry_scheduled"
    _assert_complete_analysis_finalization(client, operation_id=queued["id"])
    with client.app.state.session_factory() as db:
        operation = db.get(WorkflowJobRecord, queued["id"])
        assert operation is not None
        usage = db.get(UsageEventRecord, operation.usage_event_id)
        assert usage is not None
        first_settled_at = usage.settled_at
        assert first_settled_at is not None

    monkeypatch.setattr(WorkflowJobRepository, "save", original_save)
    with client.app.state.session_factory() as db:
        retry = db.get(WorkflowJobRecord, queued["id"])
        assert retry is not None
        retry.available_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
        settled = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="post-finalizer-recovery-worker",
        )

    assert settled.status == "succeeded"
    _assert_complete_analysis_finalization(client, operation_id=queued["id"])
    with client.app.state.session_factory() as db:
        operation = db.get(WorkflowJobRecord, queued["id"])
        assert operation is not None
        usage = db.get(UsageEventRecord, operation.usage_event_id)
        assert usage is not None
        assert usage.settled_at == first_settled_at


def test_completed_analysis_replay_repairs_missing_downstream_state(
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
        idempotency_key="analysis-finalization-repair",
    )
    assert response.status_code == 202
    assert queued is not None

    with client.app.state.session_factory() as db:
        first = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="initial-worker",
        )
    assert first.status == "succeeded"

    with client.app.state.session_factory() as db:
        operation = db.get(WorkflowJobRecord, queued["id"])
        assert operation is not None
        analysis = db.scalar(
            select(AnalysisRecord).where(AnalysisRecord.workflow_job_id == operation.id)
        )
        assert analysis is not None
        application = db.scalar(
            select(ApplicationRecord).where(
                ApplicationRecord.user_id == operation.user_id,
                ApplicationRecord.report_id == analysis.id,
            )
        )
        assert application is not None
        db.delete(application)
        for audit in db.scalars(
            select(AuditEventRecord).where(
                AuditEventRecord.user_id == operation.user_id,
                AuditEventRecord.event_type.in_({"application.analyzed", "job.analyzed"}),
            )
        ):
            db.delete(audit)
        usage = db.get(UsageEventRecord, operation.usage_event_id)
        assert usage is not None
        usage.state = "reserved"
        usage.settled_at = None
        usage.metadata_json = {"status": "reserved"}
        operation.status = "retry_scheduled"
        operation.stage = "retry_scheduled"
        operation.available_at = datetime.now(UTC) - timedelta(seconds=1)
        operation.analysis_id = None
        operation.result_json = {}
        operation.finished_at = None
        db.commit()

        repaired = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="repair-worker",
        )

    assert repaired.status == "succeeded"
    _assert_complete_analysis_finalization(client, operation_id=queued["id"])

    with client.app.state.session_factory() as db:
        operation = db.get(WorkflowJobRecord, queued["id"])
        assert operation is not None
        usage = db.get(UsageEventRecord, operation.usage_event_id)
        assert usage is not None
        first_settled_at = usage.settled_at
        assert first_settled_at is not None
        operation.status = "retry_scheduled"
        operation.stage = "retry_scheduled"
        operation.available_at = datetime.now(UTC) - timedelta(seconds=1)
        operation.finished_at = None
        db.commit()
        replayed = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="replay-worker",
        )

    assert replayed.status == "succeeded"
    _assert_complete_analysis_finalization(client, operation_id=queued["id"])
    with client.app.state.session_factory() as db:
        replayed_operation = db.get(WorkflowJobRecord, queued["id"])
        assert replayed_operation is not None
        replayed_usage = db.get(UsageEventRecord, replayed_operation.usage_event_id)
        assert replayed_usage is not None
        assert replayed_usage.settled_at == first_settled_at


def test_older_completed_replay_preserves_newer_application_analysis_and_draft(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)
    preview = client.post("/jobs/preview", json={"job_text": sample_job_text})
    assert preview.status_code == 200
    draft_response = client.post(
        "/applications",
        json={
            "source_type": "pasted_text",
            "job_text": sample_job_text,
            "reviewed_job_text": sample_job_text,
            "reviewed_job_profile": preview.json()["profile"],
            "resume_id": resume_id,
        },
    )
    assert draft_response.status_code == 201
    application_id = draft_response.json()["id"]
    payload = {"resume_id": resume_id, "application_id": application_id}

    first_response, first_queued = submit_analysis(
        client,
        payload,
        idempotency_key="analysis-superseded-first",
    )
    assert first_response.status_code == 202
    assert first_queued is not None
    with client.app.state.session_factory() as db:
        first = execute_workflow_job(
            db,
            first_queued["id"],
            settings=settings,
            worker_id="superseded-first-worker",
        )
    assert first.status == "succeeded"

    second_response, second_queued = submit_analysis(
        client,
        payload,
        idempotency_key="analysis-superseded-second",
    )
    assert second_response.status_code == 202
    assert second_queued is not None
    with client.app.state.session_factory() as db:
        second = execute_workflow_job(
            db,
            second_queued["id"],
            settings=settings,
            worker_id="superseded-second-worker",
        )
        assert second.status == "succeeded"
        second_analysis = db.scalar(
            select(AnalysisRecord).where(AnalysisRecord.workflow_job_id == second_queued["id"])
        )
        application = db.get(ApplicationRecord, application_id)
        assert second_analysis is not None
        assert application is not None
        assert application.report_id == second_analysis.id
        newer_draft = TailoredResumeDraftRecord(
            user_id=application.user_id,
            application_id=application.id,
            report_id=second_analysis.id,
            status="reviewed",
            items_json=[],
        )
        db.add(newer_draft)
        db.commit()
        newer_draft_id = newer_draft.id
        second_analysis_id = second_analysis.id

    with client.app.state.session_factory() as db:
        old_operation = db.get(WorkflowJobRecord, first_queued["id"])
        assert old_operation is not None
        old_operation.status = "retry_scheduled"
        old_operation.stage = "retry_scheduled"
        old_operation.available_at = datetime.now(UTC) - timedelta(seconds=1)
        old_operation.finished_at = None
        db.commit()
        replayed = execute_workflow_job(
            db,
            first_queued["id"],
            settings=settings,
            worker_id="superseded-replay-worker",
        )

    assert replayed.status == "succeeded"
    with client.app.state.session_factory() as db:
        application = db.get(ApplicationRecord, application_id)
        newer_draft = db.get(TailoredResumeDraftRecord, newer_draft_id)
        assert application is not None
        assert application.analysis_id == second_analysis_id
        assert application.report_id == second_analysis_id
        assert newer_draft is not None
        assert newer_draft.report_id == second_analysis_id
        assert _analysis_audit_counts(db, user_id=application.user_id) == {
            "application.analyzed": 2,
            "job.analyzed": 2,
        }


def test_stale_worker_cannot_overwrite_reclaimed_workflow_state(
    client,
    monkeypatch,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    resume_id = _upload_resume(client, sample_resume_text)
    response, queued = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="analysis-stale-worker-fence",
    )
    assert response.status_code == 202
    assert queued is not None

    def simulate_reclaim(*_args, **_kwargs):
        with client.app.state.session_factory() as replacement_db:
            replacement = replacement_db.get(WorkflowJobRecord, queued["id"])
            assert replacement is not None
            replacement.status = "running"
            replacement.lease_owner = "score-v2:replacement-worker"
            replacement.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
            replacement_db.commit()
        raise RuntimeError("stale worker resumed after lease reassignment")

    monkeypatch.setattr(
        "app.services.workflow_job_service.analyze_job",
        simulate_reclaim,
    )
    with client.app.state.session_factory() as db:
        observed = execute_workflow_job(
            db,
            queued["id"],
            settings=settings,
            worker_id="stale-worker",
        )

    assert observed.status == "running"
    assert observed.lease_owner == "score-v2:replacement-worker"
    with client.app.state.session_factory() as db:
        persisted = db.get(WorkflowJobRecord, queued["id"])
        usage = db.get(UsageEventRecord, observed.usage_event_id)
        assert persisted is not None
        assert persisted.status == "running"
        assert persisted.stage == "starting"
        assert persisted.lease_owner == "score-v2:replacement-worker"
        assert persisted.error_code is None
        assert usage is not None
        assert usage.state == "reserved"


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
        record.lease_owner = "score-v2:crashed-worker"
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
        record.lease_owner = "score-v2:crashed-worker"
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
        record.lease_owner = "score-v2:active-worker"
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
            lease_owner="score-v2:active-worker",
            lease_seconds=60,
            now=heartbeat_at,
        )
        db.refresh(record)

    assert record.heartbeat_at.replace(tzinfo=UTC) == heartbeat_at
    assert record.lease_expires_at.replace(tzinfo=UTC) == heartbeat_at + timedelta(seconds=60)


def test_worker_progress_updates_only_the_current_lease_owner(
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
        idempotency_key="analysis-progress-owner-fence",
    )
    assert response.status_code == 202
    assert queued is not None

    with client.app.state.session_factory() as db:
        record = db.get(WorkflowJobRecord, queued["id"])
        assert record is not None
        record.status = "running"
        record.stage = "replacement_started"
        record.progress_percent = 35
        record.lease_owner = "score-v2:replacement-worker"
        record.lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
        db.commit()

        _update_progress(
            db,
            record.id,
            stage="stale_progress",
            progress=80,
            lease_owner="stale-worker",
        )
        db.refresh(record)
        assert record.stage == "replacement_started"
        assert record.progress_percent == 35

        _update_progress(
            db,
            record.id,
            stage="current_progress",
            progress=80,
            lease_owner="score-v2:replacement-worker",
        )
        db.refresh(record)
        assert record.stage == "current_progress"
        assert record.progress_percent == 80


def _upload_resume(client, resume_text: str) -> int:
    response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
    )
    assert response.status_code == 201
    return response.json()["resume_id"]


def _assert_complete_analysis_finalization(client, *, operation_id: str) -> None:
    with client.app.state.session_factory() as db:
        operation = db.get(WorkflowJobRecord, operation_id)
        assert operation is not None
        analyses = list(
            db.scalars(select(AnalysisRecord).where(AnalysisRecord.workflow_job_id == operation_id))
        )
        assert len(analyses) == 1
        analysis = analyses[0]
        assert analysis.status == "completed"
        applications = list(
            db.scalars(
                select(ApplicationRecord).where(
                    ApplicationRecord.user_id == operation.user_id,
                    ApplicationRecord.report_id == analysis.id,
                )
            )
        )
        assert len(applications) == 1
        assert applications[0].analysis_id == analysis.id
        assert _analysis_audit_counts(db, user_id=operation.user_id) == {
            "application.analyzed": 1,
            "job.analyzed": 1,
        }
        usage = db.get(UsageEventRecord, operation.usage_event_id)
        assert usage is not None
        assert usage.state == "consumed"
        assert usage.metadata_json["analysis_id"] == analysis.id
        assert usage.metadata_json["report_id"] == analysis.id


def _analysis_audit_counts(db, *, user_id: int) -> dict[str, int]:
    records = list(
        db.scalars(
            select(AuditEventRecord).where(
                AuditEventRecord.user_id == user_id,
                AuditEventRecord.event_type.in_({"application.analyzed", "job.analyzed"}),
            )
        )
    )
    return {
        event_type: sum(record.event_type == event_type for record in records)
        for event_type in ("application.analyzed", "job.analyzed")
    }

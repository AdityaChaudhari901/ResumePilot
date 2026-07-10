import os
from datetime import timedelta
from threading import Event, Thread
from uuid import uuid4

from sqlalchemy import select

from app.db.models import (
    AnalysisRecord,
    ApplicationRecord,
    AuditEventRecord,
    JobRecord,
    ResumeRecord,
    TailoredResumeDraftRecord,
    UsageEventRecord,
    UserRecord,
    WorkflowJobRecord,
    utc_now,
)
from app.repositories.workflow_jobs import WorkflowJobRepository
from app.schemas.job import JobAnalysisResponse
from app.services.workflow_job_service import execute_workflow_job
from tests.api_helpers import submit_analysis, successful_analysis


def test_audit_events_are_recorded_without_raw_resume_or_job_text(
    client, sample_resume_text, sample_job_text
):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    markdown_response = client.post(f"/reports/{body['report_id']}/markdown")
    assert markdown_response.status_code == 200

    events_response = client.get("/audit/events")

    assert events_response.status_code == 200
    events = events_response.json()["events"]
    event_types = [event["event_type"] for event in events]
    assert "resume.uploaded" in event_types
    assert "job.analyzed" in event_types
    assert "report.exported" in event_types
    serialized_events = str(events)
    assert "aarav@example.com" not in serialized_events
    assert sample_resume_text not in serialized_events
    assert sample_job_text not in serialized_events


def test_delete_report_removes_analysis_and_writes_audit_event(
    client, settings, sample_resume_text, sample_job_text, monkeypatch
):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)

    applications = client.get("/applications").json()["items"]
    application_id = applications[0]["id"]
    draft = client.get(f"/applications/{application_id}/tailored-resume").json()
    for item in draft["items"]:
        accepted = client.patch(
            f"/applications/{application_id}/tailored-resume/items/{item['id']}",
            json={"status": "accepted"},
        )
        assert accepted.status_code == 200

    monkeypatch.setattr(
        "app.services.tailored_resume_service.compile_latex_to_pdf",
        lambda *_args, **_kwargs: b"%PDF-1.7\nprivacy cleanup test\n",
    )
    export_response = client.post(
        f"/applications/{application_id}/tailored-resume/pdf",
        headers={"Idempotency-Key": "privacy-report-pdf-export"},
    )
    assert export_response.status_code == 202
    export_operation = export_response.json()
    assert export_operation["status"] == "succeeded"

    session_factory = client.app.state.session_factory
    with session_factory() as db:
        workflow_jobs = list(db.scalars(select(WorkflowJobRecord)))
        assert len(workflow_jobs) == 2
        user_id = workflow_jobs[0].user_id
        analysis_operation = next(job for job in workflow_jobs if job.kind == "analysis")
        assert analysis_operation.payload_json["job_text"] == sample_job_text.strip()
        operation_ids = {job.id for job in workflow_jobs}
        usage_event_ids = {job.usage_event_id for job in workflow_jobs}
        export_path = settings.export_dir / str(user_id) / f"{export_operation['id']}.pdf"
        assert export_path.is_file()

    delete_response = client.delete(f"/reports/{body['report_id']}")

    assert delete_response.status_code == 200
    delete_body = delete_response.json()
    assert delete_body["report_id"] == body["report_id"]
    assert delete_body["deleted_reports"] == 1
    assert delete_body["deleted_workflow_jobs"] == 2
    assert delete_body["deleted_export_files"] == 1
    assert delete_body["audit_event_id"]
    assert client.get(f"/reports/{body['report_id']}").status_code == 404
    assert not export_path.exists()
    for operation_id in operation_ids:
        assert client.get(f"/operations/{operation_id}").status_code == 404

    with session_factory() as db:
        assert (
            list(
                db.scalars(select(WorkflowJobRecord).where(WorkflowJobRecord.id.in_(operation_ids)))
            )
            == []
        )
        usage_events = list(
            db.scalars(select(UsageEventRecord).where(UsageEventRecord.id.in_(usage_event_ids)))
        )
        assert {event.metadata_json["status"] for event in usage_events} == {"privacy_deleted"}
        assert sample_job_text not in str([event.metadata_json for event in usage_events])

    events_response = client.get("/audit/events?event_type=report.deleted")
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert events[0]["payload"]["report_id"] == body["report_id"]


def test_delete_resume_removes_resume_reports_upload_and_writes_audit_event(
    client, settings, sample_resume_text, sample_job_text
):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    upload_files_before = list(settings.upload_dir.glob("users/*/*"))
    assert upload_files_before

    delete_response = client.delete(f"/resumes/{body['resume_id']}")

    assert delete_response.status_code == 200
    delete_body = delete_response.json()
    assert delete_body["resume_id"] == body["resume_id"]
    assert delete_body["deleted_resumes"] == 1
    assert delete_body["deleted_reports"] == 1
    assert delete_body["deleted_upload_files"] == 1
    assert delete_body["deleted_workflow_jobs"] == 1
    assert client.get(f"/reports/{body['report_id']}").status_code == 404
    assert list(settings.upload_dir.glob("users/*/*")) == []

    events_response = client.get("/audit/events?event_type=resume.deleted")
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert events[0]["payload"]["resume_id"] == body["resume_id"]


def test_delete_resume_removes_queued_workflow_payload_and_releases_quota(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", sample_resume_text.encode(), "text/markdown")},
    )
    resume_id = upload_response.json()["resume_id"]
    response, operation = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="privacy-delete-queued-analysis",
    )
    assert response.status_code == 202
    assert operation is not None and operation["status"] == "queued"

    with client.app.state.session_factory() as db:
        workflow_job = db.get(WorkflowJobRecord, operation["id"])
        assert workflow_job is not None
        assert workflow_job.payload_json["job_text"] == sample_job_text.strip()
        usage_event_id = workflow_job.usage_event_id

    delete_response = client.delete(f"/resumes/{resume_id}")

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_workflow_jobs"] == 1
    with client.app.state.session_factory() as db:
        assert db.get(WorkflowJobRecord, operation["id"]) is None
        usage_event = db.get(UsageEventRecord, usage_event_id)
        assert usage_event is not None
        assert usage_event.state == "released"
        assert usage_event.metadata_json == {
            "status": "privacy_deleted",
            "previous_state": "reserved",
        }
    assert client.get("/usage/summary").json()["limits"][0]["used"] == 0


def test_delete_resume_tombstones_running_job_without_worker_resurrection(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
    monkeypatch,
):
    settings.workflow_inline_execution = False
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", sample_resume_text.encode(), "text/markdown")},
    )
    resume_id = upload_response.json()["resume_id"]
    response, operation = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="privacy-delete-running-analysis",
    )
    assert response.status_code == 202
    assert operation is not None

    worker_started = Event()
    finish_worker = Event()
    worker_errors: list[BaseException] = []

    def blocked_analysis(*_args, **_kwargs) -> JobAnalysisResponse:
        worker_started.set()
        assert finish_worker.wait(timeout=5)
        return JobAnalysisResponse(
            analysis_id=999,
            report_id=999,
            match_score=50,
            status="completed",
        )

    monkeypatch.setattr(
        "app.services.workflow_job_service.analyze_job",
        blocked_analysis,
    )

    def run_worker() -> None:
        try:
            with client.app.state.session_factory() as db:
                execute_workflow_job(
                    db,
                    operation["id"],
                    settings=settings,
                    worker_id="privacy-regression-worker",
                )
        except BaseException as exc:  # pragma: no cover - asserted below
            worker_errors.append(exc)

    worker = Thread(target=run_worker, daemon=True)
    worker.start()
    assert worker_started.wait(timeout=5)
    try:
        delete_response = client.delete(f"/resumes/{resume_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["deleted_workflow_jobs"] == 0
        assert delete_response.json()["scrubbed_workflow_jobs"] == 1
        with client.app.state.session_factory() as db:
            tombstone = db.get(WorkflowJobRecord, operation["id"])
            assert tombstone is not None
            assert tombstone.status == "cancel_requested"
            assert tombstone.payload_json == {}
            assert tombstone.result_json == {}
            assert tombstone.error_code is None
            assert tombstone.error_message is None
            assert tombstone.request_id is None
    finally:
        finish_worker.set()
        worker.join(timeout=5)

    assert not worker.is_alive()
    assert worker_errors == []
    with client.app.state.session_factory() as db:
        tombstone = db.get(WorkflowJobRecord, operation["id"])
        assert tombstone is not None
        assert tombstone.status == "canceled"
        assert tombstone.payload_json == {}
        assert tombstone.result_json == {}
        assert db.get(ResumeRecord, resume_id) is None


def test_retention_purge_uses_configured_retention_window(
    client, settings, sample_resume_text, sample_job_text
):
    settings.data_retention_days = 1
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)

    session_factory = client.app.state.session_factory
    with session_factory() as db:
        old = utc_now() - timedelta(days=2)
        resume = db.get(ResumeRecord, body["resume_id"])
        analysis = db.get(AnalysisRecord, body["analysis_id"])
        assert resume is not None
        assert analysis is not None
        resume.created_at = old
        analysis.created_at = old
        db.commit()

    purge_response = client.post("/retention/purge")

    assert purge_response.status_code == 200
    purge_body = purge_response.json()
    assert purge_body["retention_enabled"] is True
    assert purge_body["retention_days"] == 1
    assert purge_body["deleted_resumes"] == 1
    assert purge_body["deleted_reports"] == 1
    assert purge_body["deleted_upload_files"] == 1
    assert client.get(f"/reports/{body['report_id']}").status_code == 404


def test_retention_purge_removes_stale_workflow_payload_and_local_artifact(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.data_retention_days = 1
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    old = utc_now() - timedelta(days=2)

    with client.app.state.session_factory() as db:
        workflow_job = db.scalar(
            select(WorkflowJobRecord).where(WorkflowJobRecord.analysis_id == body["analysis_id"])
        )
        assert workflow_job is not None
        workflow_job.created_at = old
        workflow_job.updated_at = old
        operation_id = workflow_job.id
        usage_event_id = workflow_job.usage_event_id
        artifact_path = settings.export_dir / str(workflow_job.user_id) / f"{operation_id}.pdf"
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_bytes(b"%PDF-1.7\nstale artifact\n")
        timestamp = old.timestamp()
        os.utime(artifact_path, (timestamp, timestamp))
        db.commit()

    purge_response = client.post("/retention/purge")

    assert purge_response.status_code == 200
    purge = purge_response.json()
    assert purge["deleted_workflow_jobs"] == 1
    assert purge["deleted_export_files"] == 1
    assert client.get(f"/reports/{body['report_id']}").status_code == 200
    assert not artifact_path.exists()
    with client.app.state.session_factory() as db:
        assert db.get(WorkflowJobRecord, operation_id) is None
        analysis = db.get(AnalysisRecord, body["analysis_id"])
        assert analysis is not None
        assert analysis.workflow_job_id is None
        usage = db.get(UsageEventRecord, usage_event_id)
        assert usage is not None
        assert usage.metadata_json["status"] == "privacy_deleted"


def test_retention_tombstones_active_leased_workflow_instead_of_deleting_it(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    settings.workflow_inline_execution = False
    settings.data_retention_days = 1
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", sample_resume_text.encode(), "text/markdown")},
    )
    resume_id = upload_response.json()["resume_id"]
    response, operation = submit_analysis(
        client,
        {"resume_id": resume_id, "job_text": sample_job_text},
        idempotency_key="privacy-retention-running-analysis",
    )
    assert response.status_code == 202
    assert operation is not None
    old = utc_now() - timedelta(days=2)

    with client.app.state.session_factory() as db:
        leased = WorkflowJobRepository(db).claim_by_id(
            operation["id"],
            worker_id="active-retention-worker",
            lease_expires_at=utc_now() + timedelta(minutes=3),
        )
        assert leased is not None
        leased.created_at = old
        db.add(leased)
        db.commit()

    purge_response = client.post("/retention/purge")

    assert purge_response.status_code == 200
    purge = purge_response.json()
    assert purge["deleted_workflow_jobs"] == 0
    assert purge["scrubbed_workflow_jobs"] == 1
    with client.app.state.session_factory() as db:
        tombstone = db.get(WorkflowJobRecord, operation["id"])
        assert tombstone is not None
        assert tombstone.status == "cancel_requested"
        assert tombstone.payload_json == {}
        assert tombstone.result_json == {}
        assert tombstone.lease_owner == "score-v2:active-retention-worker"


def test_retention_purge_noops_when_retention_is_disabled(client):
    purge_response = client.post("/retention/purge")

    assert purge_response.status_code == 200
    purge_body = purge_response.json()
    assert purge_body["retention_enabled"] is False
    assert purge_body["audit_event_id"] is None


def test_account_delete_erases_only_current_tenant_and_does_not_follow_symlinks(
    client,
    settings,
    sample_resume_text,
    sample_job_text,
):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    other_headers = {
        "X-ResumePilot-User": "privacy-other-user",
        "X-ResumePilot-Email": "other@example.com",
        "X-ResumePilot-Name": "Other User",
    }
    other_upload = client.post(
        "/resumes/upload",
        files={"file": ("other.md", sample_resume_text.encode(), "text/markdown")},
        headers=other_headers,
    )
    assert other_upload.status_code == 201
    other_resume_id = other_upload.json()["resume_id"]

    with client.app.state.session_factory() as db:
        analysis = db.get(AnalysisRecord, body["analysis_id"])
        other_resume = db.get(ResumeRecord, other_resume_id)
        assert analysis is not None and other_resume is not None
        user_id = analysis.user_id
        other_user_id = other_resume.user_id

    orphan_upload = settings.upload_dir / "users" / str(user_id) / "orphan.bin"
    orphan_upload.parent.mkdir(parents=True, exist_ok=True)
    orphan_upload.write_bytes(b"sensitive orphan upload")
    outside_file = settings.data_dir / "outside-export.pdf"
    outside_file.write_bytes(b"must not be deleted")
    tenant_export_dir = settings.export_dir / str(user_id)
    tenant_export_dir.mkdir(parents=True, exist_ok=True)
    (tenant_export_dir / f"{uuid4()}.pdf").symlink_to(outside_file)

    missing_confirmation = client.delete("/account")
    assert missing_confirmation.status_code == 422
    response = client.delete(
        "/account",
        headers={"X-Confirm-Account-Deletion": "delete-my-account"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["account_deleted"] is True
    assert result["deleted_resumes"] == 1
    assert result["deleted_reports"] == 1
    assert result["deleted_workflow_jobs"] == 1
    assert result["deleted_upload_files"] >= 2
    assert result["deleted_export_files"] == 1
    assert outside_file.read_bytes() == b"must not be deleted"
    assert not (settings.upload_dir / "users" / str(user_id)).exists()
    assert not tenant_export_dir.exists()

    tenant_models = (
        ResumeRecord,
        AnalysisRecord,
        JobRecord,
        ApplicationRecord,
        TailoredResumeDraftRecord,
        AuditEventRecord,
        UsageEventRecord,
        WorkflowJobRecord,
    )
    with client.app.state.session_factory() as db:
        assert db.get(UserRecord, user_id) is None
        assert db.get(UserRecord, other_user_id) is not None
        assert db.get(ResumeRecord, other_resume_id) is not None
        for model in tenant_models:
            assert list(db.scalars(select(model).where(model.user_id == user_id))) == []


def _upload_and_analyze(client, resume_text: str, job_text: str) -> dict:
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
    )
    assert upload_response.status_code == 201
    resume_id = upload_response.json()["resume_id"]

    body = successful_analysis(
        client,
        {"resume_id": resume_id, "job_text": job_text},
    )
    body["resume_id"] = resume_id
    return body

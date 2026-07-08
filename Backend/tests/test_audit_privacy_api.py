from datetime import timedelta

from app.db.models import AnalysisRecord, ResumeRecord, utc_now


def test_audit_events_are_recorded_without_raw_resume_or_job_text(
    client, sample_resume_text, sample_job_text
):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    markdown_response = client.get(f"/reports/{body['report_id']}/markdown")
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
    client, sample_resume_text, sample_job_text
):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)

    delete_response = client.delete(f"/reports/{body['report_id']}")

    assert delete_response.status_code == 200
    delete_body = delete_response.json()
    assert delete_body["report_id"] == body["report_id"]
    assert delete_body["deleted_reports"] == 1
    assert delete_body["audit_event_id"]
    assert client.get(f"/reports/{body['report_id']}").status_code == 404

    events_response = client.get("/audit/events?event_type=report.deleted")
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert events[0]["payload"]["report_id"] == body["report_id"]


def test_delete_resume_removes_resume_reports_upload_and_writes_audit_event(
    client, settings, sample_resume_text, sample_job_text
):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    upload_files_before = list(settings.upload_dir.iterdir())
    assert upload_files_before

    delete_response = client.delete(f"/resumes/{body['resume_id']}")

    assert delete_response.status_code == 200
    delete_body = delete_response.json()
    assert delete_body["resume_id"] == body["resume_id"]
    assert delete_body["deleted_resumes"] == 1
    assert delete_body["deleted_reports"] == 1
    assert delete_body["deleted_upload_files"] == 1
    assert client.get(f"/reports/{body['report_id']}").status_code == 404
    assert list(settings.upload_dir.iterdir()) == []

    events_response = client.get("/audit/events?event_type=resume.deleted")
    assert events_response.status_code == 200
    events = events_response.json()["events"]
    assert events[0]["payload"]["resume_id"] == body["resume_id"]


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


def test_retention_purge_noops_when_retention_is_disabled(client):
    purge_response = client.post("/retention/purge")

    assert purge_response.status_code == 200
    purge_body = purge_response.json()
    assert purge_body["retention_enabled"] is False
    assert purge_body["audit_event_id"] is None


def _upload_and_analyze(client, resume_text: str, job_text: str) -> dict:
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
    )
    assert upload_response.status_code == 201
    resume_id = upload_response.json()["resume_id"]

    analyze_response = client.post(
        "/jobs/analyze",
        json={"resume_id": resume_id, "job_text": job_text},
    )
    assert analyze_response.status_code == 200
    body = analyze_response.json()
    body["resume_id"] = resume_id
    return body

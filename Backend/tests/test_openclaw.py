from sqlalchemy import select

from app.db.models import ApplicationRecord, AuditEventRecord, UsageEventRecord


def test_openclaw_endpoint_requires_valid_token(client, sample_job_text):
    response = client.post(
        "/chat/openclaw",
        json={
            "command": "job",
            "args": sample_job_text,
            "sender": "telegram:12345",
            "session_id": "telegram:slash:12345",
        },
    )

    assert response.status_code == 401


def test_openclaw_endpoint_analyzes_latest_resume(client, sample_resume_text, sample_job_text):
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
    )
    assert upload_response.status_code == 201

    response = client.post(
        "/chat/openclaw",
        headers={"Authorization": "Bearer test-token"},
        json={
            "command": "job",
            "args": f"paste:{sample_job_text}",
            "sender": "telegram:12345",
            "session_id": "telegram:slash:12345",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["analysis_id"] is not None
    assert "# Job Fit Report" in body["markdown"]

    with client.app.state.session_factory() as db:
        application = db.scalar(
            select(ApplicationRecord).where(ApplicationRecord.report_id == body["report_id"])
        )
        assert application is not None
        assert application.analysis_id == body["analysis_id"]
        audit_types = set(
            db.scalars(
                select(AuditEventRecord.event_type).where(
                    AuditEventRecord.event_type.in_({"application.analyzed", "job.analyzed"})
                )
            )
        )
        assert audit_types == {"application.analyzed", "job.analyzed"}
        usage = db.scalar(
            select(UsageEventRecord).where(
                UsageEventRecord.event_type == "analysis_created",
                UsageEventRecord.metadata_json["analysis_id"].as_integer() == body["analysis_id"],
            )
        )
        assert usage is not None
        assert usage.state == "consumed"

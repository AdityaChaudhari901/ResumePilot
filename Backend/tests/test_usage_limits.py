from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.schemas.agent import AgentWorkflowMode

USER_A_HEADERS = {
    "X-ResumePilot-User": "usage-user-a",
    "X-ResumePilot-Email": "usage-a@example.com",
    "X-ResumePilot-Name": "Usage User A",
}
USER_B_HEADERS = {
    "X-ResumePilot-User": "usage-user-b",
    "X-ResumePilot-Email": "usage-b@example.com",
    "X-ResumePilot-Name": "Usage User B",
}


def test_usage_summary_starts_with_free_plan_limits(client):
    response = client.get("/usage/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["subscription_status"] == "inactive"
    assert body["live_crewai_enabled"] is False
    assert _limit(body, "analyses") == {"used": 0, "limit": 3, "remaining": 3}
    assert _limit(body, "exports") == {"used": 0, "limit": 5, "remaining": 5}
    assert _limit(body, "crewai_runs") == {"used": 0, "limit": 0, "remaining": 0}


def test_configured_dev_user_can_start_on_paid_local_plan(tmp_path):
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-dev-plan.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        DEV_USER_PLAN="premium",
        DEV_USER_SUBSCRIPTION_STATUS="active",
    )
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get("/usage/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "premium"
    assert body["subscription_status"] == "active"
    assert body["live_crewai_enabled"] is True
    assert _limit(body, "analyses") == {"used": 0, "limit": 500, "remaining": 500}


def test_paid_local_plan_seed_only_applies_to_configured_dev_user(tmp_path):
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-tenant-plan.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        DEV_USER_PLAN="premium",
        DEV_USER_SUBSCRIPTION_STATUS="active",
    )
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get(
            "/usage/summary",
            headers={
                "X-ResumePilot-User": "non-dev-user",
                "X-ResumePilot-Email": "non-dev@example.com",
                "X-ResumePilot-Name": "Non Dev User",
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert body["plan"] == "free"
    assert body["subscription_status"] == "inactive"
    assert body["live_crewai_enabled"] is False


def test_analysis_usage_is_metered_and_limited(client, sample_resume_text, sample_job_text):
    resume_id = _upload_resume(client, sample_resume_text)

    for index in range(3):
        response = client.post(
            "/jobs/analyze",
            json={
                "resume_id": resume_id,
                "job_text": f"{sample_job_text}\nRun marker: {index}",
            },
        )
        assert response.status_code == 200

    summary = client.get("/usage/summary").json()
    assert _limit(summary, "analyses") == {"used": 3, "limit": 3, "remaining": 0}

    blocked_response = client.post(
        "/jobs/analyze",
        json={"resume_id": resume_id, "job_text": f"{sample_job_text}\nRun marker: blocked"},
    )

    assert blocked_response.status_code == 402
    assert blocked_response.json()["detail"]["code"] == "plan_limit_reached"
    assert blocked_response.json()["detail"]["metric"] == "analyses"


def test_export_usage_is_metered_and_limited(client, sample_resume_text, sample_job_text):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)

    for _ in range(5):
        response = client.get(f"/reports/{body['report_id']}/markdown")
        assert response.status_code == 200

    summary = client.get("/usage/summary").json()
    assert _limit(summary, "exports") == {"used": 5, "limit": 5, "remaining": 0}

    blocked_response = client.get(f"/reports/{body['report_id']}/resume/latex")

    assert blocked_response.status_code == 402
    assert blocked_response.json()["detail"]["code"] == "plan_limit_reached"
    assert blocked_response.json()["detail"]["metric"] == "exports"


def test_usage_summary_is_tenant_scoped(client, sample_resume_text, sample_job_text):
    _upload_and_analyze(
        client,
        sample_resume_text,
        sample_job_text,
        headers=USER_A_HEADERS,
    )

    user_a_summary = client.get("/usage/summary", headers=USER_A_HEADERS).json()
    user_b_summary = client.get("/usage/summary", headers=USER_B_HEADERS).json()

    assert _limit(user_a_summary, "analyses")["used"] == 1
    assert _limit(user_b_summary, "analyses")["used"] == 0


def test_free_plan_downgrades_crewai_without_consuming_live_runs(
    client, monkeypatch, sample_resume_text, sample_job_text, settings
):
    settings.agent_workflow_mode = AgentWorkflowMode.crewai

    def unexpected_runner(_settings):
        raise AssertionError("Free plans must not attempt live CrewAI execution")

    monkeypatch.setattr(
        "app.services.agent_workflow.build_crewai_workflow_runner",
        unexpected_runner,
    )

    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    trace_response = client.get(f"/reports/{body['report_id']}/trace")
    summary = client.get("/usage/summary").json()

    assert trace_response.status_code == 200
    assert trace_response.json()["trace"]["mode"] == AgentWorkflowMode.deterministic_fallback
    assert _limit(summary, "crewai_runs") == {"used": 0, "limit": 0, "remaining": 0}


def _upload_and_analyze(
    client,
    resume_text: str,
    job_text: str,
    *,
    headers: dict[str, str] | None = None,
) -> dict:
    resume_id = _upload_resume(client, resume_text, headers=headers)
    analyze_response = client.post(
        "/jobs/analyze",
        json={"resume_id": resume_id, "job_text": job_text},
        headers=headers,
    )
    assert analyze_response.status_code == 200
    body = analyze_response.json()
    body["resume_id"] = resume_id
    return body


def _upload_resume(client, resume_text: str, *, headers: dict[str, str] | None = None) -> int:
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    return upload_response.json()["resume_id"]


def _limit(summary: dict, metric: str) -> dict[str, int | None]:
    item = next(limit for limit in summary["limits"] if limit["metric"] == metric)
    return {
        "used": item["used"],
        "limit": item["limit"],
        "remaining": item["remaining"],
    }

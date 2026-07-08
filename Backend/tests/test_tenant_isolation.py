from fastapi.testclient import TestClient

from app.main import create_app

USER_A_HEADERS = {
    "X-ResumePilot-User": "user-a",
    "X-ResumePilot-Email": "a@example.com",
    "X-ResumePilot-Name": "User A",
}
USER_B_HEADERS = {
    "X-ResumePilot-User": "user-b",
    "X-ResumePilot-Email": "b@example.com",
    "X-ResumePilot-Name": "User B",
}


def test_reports_resumes_and_audit_events_are_tenant_scoped(
    client, sample_resume_text, sample_job_text
):
    user_a = _upload_and_analyze(
        client,
        sample_resume_text,
        sample_job_text,
        headers=USER_A_HEADERS,
    )

    assert client.get(f"/reports/{user_a['report_id']}", headers=USER_A_HEADERS).status_code == 200
    assert client.get("/audit/events", headers=USER_A_HEADERS).json()["count"] > 0

    assert client.get(f"/reports/{user_a['report_id']}", headers=USER_B_HEADERS).status_code == 404
    assert (
        client.get(f"/reports/{user_a['report_id']}/markdown", headers=USER_B_HEADERS).status_code
        == 404
    )
    assert (
        client.delete(f"/reports/{user_a['report_id']}", headers=USER_B_HEADERS).status_code == 404
    )
    assert (
        client.post(
            "/jobs/analyze",
            json={"resume_id": user_a["resume_id"], "job_text": sample_job_text},
            headers=USER_B_HEADERS,
        ).status_code
        == 404
    )
    assert client.get("/audit/events", headers=USER_B_HEADERS).json()["events"] == []


def test_same_resume_file_is_deduplicated_per_tenant_not_globally(
    client, settings, sample_resume_text, sample_job_text
):
    user_a_resume_id = _upload_resume(client, sample_resume_text, headers=USER_A_HEADERS)
    user_b_resume_id = _upload_resume(client, sample_resume_text, headers=USER_B_HEADERS)

    assert user_a_resume_id != user_b_resume_id
    assert len(list(settings.upload_dir.glob("users/*/*"))) == 2

    delete_response = client.delete(f"/resumes/{user_a_resume_id}", headers=USER_A_HEADERS)

    assert delete_response.status_code == 200
    assert delete_response.json()["deleted_upload_files"] == 1
    assert len(list(settings.upload_dir.glob("users/*/*"))) == 1

    analyze_response = client.post(
        "/jobs/analyze",
        json={"resume_id": user_b_resume_id, "job_text": sample_job_text},
        headers=USER_B_HEADERS,
    )
    assert analyze_response.status_code == 200


def test_auth_required_rejects_missing_user_context(settings, sample_resume_text):
    settings.auth_required = True
    app = create_app(settings)

    with TestClient(app) as auth_client:
        response = auth_client.post(
            "/resumes/upload",
            files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing authenticated user context"


def _upload_and_analyze(
    client,
    resume_text: str,
    job_text: str,
    *,
    headers: dict[str, str],
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


def _upload_resume(client, resume_text: str, *, headers: dict[str, str]) -> int:
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    return upload_response.json()["resume_id"]

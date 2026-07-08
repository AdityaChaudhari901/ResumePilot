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

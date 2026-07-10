USER_A_HEADERS = {
    "X-ResumePilot-User": "applications-user-a",
    "X-ResumePilot-Email": "applications-a@example.com",
    "X-ResumePilot-Name": "Applications User A",
}
USER_B_HEADERS = {
    "X-ResumePilot-User": "applications-user-b",
    "X-ResumePilot-Email": "applications-b@example.com",
    "X-ResumePilot-Name": "Applications User B",
}


def test_application_draft_is_completed_by_analysis_and_status_updates(client, sample_resume_text):
    resume_id = _upload_resume(client, sample_resume_text, headers=USER_A_HEADERS)
    reviewed_profile = _reviewed_job_profile()

    draft_response = client.post(
        "/applications",
        json={
            "job_url": "https://example.com/jobs/backend-engineer",
            "reviewed_job_profile": reviewed_profile,
        },
        headers=USER_A_HEADERS,
    )

    assert draft_response.status_code == 201
    draft = draft_response.json()
    assert draft["status"] == "reviewed"
    assert draft["report_id"] is None

    analyze_response = client.post(
        "/jobs/analyze",
        json={
            "application_id": draft["id"],
            "resume_id": resume_id,
            "job_url": "https://example.com/jobs/backend-engineer",
            "reviewed_job_profile": reviewed_profile,
        },
        headers=USER_A_HEADERS,
    )

    assert analyze_response.status_code == 200
    report_id = analyze_response.json()["report_id"]

    applications_response = client.get("/applications", headers=USER_A_HEADERS)
    assert applications_response.status_code == 200
    applications = applications_response.json()["items"]
    assert len(applications) == 1
    application = applications[0]
    assert application["id"] == draft["id"]
    assert application["status"] == "analyzed"
    assert application["resume_id"] == resume_id
    assert application["report_id"] == report_id
    assert application["match_score"] >= 70

    apply_response = client.patch(
        f"/applications/{draft['id']}/status",
        json={"status": "applied"},
        headers=USER_A_HEADERS,
    )

    assert apply_response.status_code == 200
    assert apply_response.json()["status"] == "applied"


def test_report_export_marks_application_exported(client, sample_resume_text):
    resume_id = _upload_resume(client, sample_resume_text, headers=USER_A_HEADERS)
    reviewed_profile = _reviewed_job_profile()
    draft_id = client.post(
        "/applications",
        json={
            "job_url": "https://example.com/jobs/export-engineer",
            "reviewed_job_profile": reviewed_profile,
        },
        headers=USER_A_HEADERS,
    ).json()["id"]
    report_id = client.post(
        "/jobs/analyze",
        json={
            "application_id": draft_id,
            "resume_id": resume_id,
            "job_url": "https://example.com/jobs/export-engineer",
            "reviewed_job_profile": reviewed_profile,
        },
        headers=USER_A_HEADERS,
    ).json()["report_id"]

    export_response = client.post(f"/reports/{report_id}/markdown", headers=USER_A_HEADERS)

    assert export_response.status_code == 200
    application = client.get("/applications", headers=USER_A_HEADERS).json()["items"][0]
    assert application["status"] == "exported"


def test_applications_are_tenant_scoped(client, sample_resume_text):
    resume_id = _upload_resume(client, sample_resume_text, headers=USER_A_HEADERS)
    reviewed_profile = _reviewed_job_profile()
    draft_id = client.post(
        "/applications",
        json={
            "job_url": "https://example.com/jobs/tenant-engineer",
            "reviewed_job_profile": reviewed_profile,
        },
        headers=USER_A_HEADERS,
    ).json()["id"]

    assert client.get("/applications", headers=USER_B_HEADERS).json()["items"] == []
    assert (
        client.patch(
            f"/applications/{draft_id}/status",
            json={"status": "applied"},
            headers=USER_B_HEADERS,
        ).status_code
        == 404
    )
    assert (
        client.post(
            "/jobs/analyze",
            json={
                "application_id": draft_id,
                "resume_id": resume_id,
                "job_url": "https://example.com/jobs/tenant-engineer",
                "reviewed_job_profile": reviewed_profile,
            },
            headers=USER_B_HEADERS,
        ).status_code
        == 404
    )


def _upload_resume(client, resume_text: str, *, headers: dict[str, str]) -> int:
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
        headers=headers,
    )
    assert upload_response.status_code == 201
    return upload_response.json()["resume_id"]


def _reviewed_job_profile() -> dict:
    return {
        "benefits": [],
        "company": "NovaHire AI",
        "employment_type": None,
        "experience_level": "0-2 years",
        "job_id": 0,
        "keywords": ["Python", "FastAPI", "SQL"],
        "location": None,
        "preferred_skills": [],
        "required_skills": [
            {
                "confidence": "high",
                "evidence_text": "Required Python experience.",
                "id": "job_required_001",
                "importance": "required",
                "name": "Python",
            },
            {
                "confidence": "high",
                "evidence_text": "Required FastAPI experience.",
                "id": "job_required_002",
                "importance": "required",
                "name": "FastAPI",
            },
            {
                "confidence": "high",
                "evidence_text": "Required SQL database experience.",
                "id": "job_required_003",
                "importance": "required",
                "name": "SQL",
            },
        ],
        "responsibilities": ["Build REST APIs for hiring workflows."],
        "role_title": "Backend Engineer",
        "unclear_items": [],
        "warnings": [],
    }

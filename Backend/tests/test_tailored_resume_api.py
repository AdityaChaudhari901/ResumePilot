from sqlalchemy import select

from app.db.models import TailoredResumeDraftRecord
from tests.api_helpers import successful_analysis

USER_A_HEADERS = {
    "X-ResumePilot-User": "tailored-resume-user-a",
    "X-ResumePilot-Email": "tailored-a@example.com",
    "X-ResumePilot-Name": "Tailored User A",
}
USER_B_HEADERS = {
    "X-ResumePilot-User": "tailored-resume-user-b",
    "X-ResumePilot-Email": "tailored-b@example.com",
    "X-ResumePilot-Name": "Tailored User B",
}


def test_tailored_resume_draft_is_created_from_report_and_exported(client, sample_resume_text):
    application_id, _report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )

    draft_response = client.get(
        f"/applications/{application_id}/tailored-resume",
        headers=USER_A_HEADERS,
    )

    assert draft_response.status_code == 200
    draft = draft_response.json()
    assert draft["application_id"] == application_id
    assert draft["status"] == "draft"
    assert draft["pending_count"] >= 1
    assert draft["export_ready"] is False
    first_item = draft["items"][0]
    assert first_item["status"] == "pending"
    assert first_item["evidence_ids"]
    assert first_item["evidence_labels"][0].startswith("Project evidence")
    assert "summary_" not in " ".join(first_item["evidence_labels"])

    accept_response = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={"status": "accepted"},
        headers=USER_A_HEADERS,
    )

    assert accept_response.status_code == 200
    accepted_draft = accept_response.json()
    assert accepted_draft["accepted_count"] == 1
    assert accepted_draft["export_ready"] is True

    latex_response = client.post(
        f"/applications/{application_id}/tailored-resume/latex",
        headers=USER_A_HEADERS,
    )

    assert latex_response.status_code == 200
    assert latex_response.headers["content-type"].startswith("application/x-tex")
    assert (
        latex_response.headers["content-disposition"]
        == f'attachment; filename="resumepilot-application-{application_id}.tex"'
    )
    assert accepted_draft["items"][0]["suggested_bullet"] in latex_response.text

    application = client.get("/applications", headers=USER_A_HEADERS).json()["items"][0]
    assert application["status"] == "exported"


def test_tailored_resume_pdf_export_uses_only_the_accepted_application_draft(
    client,
    monkeypatch,
    sample_resume_text,
    settings,
):
    application_id, _report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )
    draft = client.get(
        f"/applications/{application_id}/tailored-resume",
        headers=USER_A_HEADERS,
    ).json()
    first_item = draft["items"][0]
    accepted = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={"status": "accepted"},
        headers=USER_A_HEADERS,
    )
    assert accepted.status_code == 200

    def fake_compile(
        latex_source: str,
        *,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> bytes:
        assert first_item["suggested_bullet"] in latex_source
        assert timeout_seconds == settings.latex_compile_timeout_seconds
        assert max_output_bytes == settings.latex_pdf_max_bytes
        return b"%PDF-1.7\n% accepted application draft\n"

    monkeypatch.setattr(
        "app.services.tailored_resume_service.compile_latex_to_pdf",
        fake_compile,
    )

    response = client.post(
        f"/applications/{application_id}/tailored-resume/pdf",
        headers={**USER_A_HEADERS, "Idempotency-Key": "pdf-export-accepted-draft"},
    )

    assert response.status_code == 202
    operation = response.json()
    assert operation["status"] == "succeeded"
    artifact_response = client.get(
        f"/operations/{operation['id']}/artifact",
        headers=USER_A_HEADERS,
    )
    assert artifact_response.status_code == 200
    assert artifact_response.headers["content-type"].startswith("application/pdf")
    assert artifact_response.content.startswith(b"%PDF-1.7")


def test_tailored_resume_rejects_accepted_unsupported_edits(client, sample_resume_text):
    application_id, _report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )
    draft = client.get(
        f"/applications/{application_id}/tailored-resume",
        headers=USER_A_HEADERS,
    ).json()
    first_item = draft["items"][0]

    response = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={
            "edited_bullet": (
                f"{first_item['suggested_bullet']} Built Docker production systems "
                "with 99% reliability."
            ),
            "status": "accepted",
        },
        headers=USER_A_HEADERS,
    )

    assert response.status_code == 422
    warning_codes = {warning["code"] for warning in response.json()["detail"]["warnings"]}
    assert "draft_bullet_has_unsupported_skill" in warning_codes
    assert "draft_bullet_has_unsupported_claim" in warning_codes


def test_tailored_resume_rejects_jd_only_skills_and_unproven_metrics(client, sample_resume_text):
    reviewed_profile = _reviewed_job_profile()
    reviewed_profile["keywords"].append("Kubernetes")
    reviewed_profile["required_skills"].append(
        {
            "confidence": "high",
            "evidence_text": "Required Kubernetes experience.",
            "id": "job_required_005",
            "importance": "required",
            "name": "Kubernetes",
        }
    )
    application_id, _report_id = _create_analyzed_application(
        client,
        sample_resume_text,
        headers=USER_A_HEADERS,
        reviewed_profile=reviewed_profile,
    )
    first_item = client.get(
        f"/applications/{application_id}/tailored-resume",
        headers=USER_A_HEADERS,
    ).json()["items"][0]

    skill_response = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={
            "edited_bullet": f"{first_item['suggested_bullet']} Used Kubernetes in deployment.",
            "status": "accepted",
        },
        headers=USER_A_HEADERS,
    )

    assert skill_response.status_code == 422
    skill_warning_codes = {
        warning["code"] for warning in skill_response.json()["detail"]["warnings"]
    }
    assert "draft_bullet_has_unsupported_skill" in skill_warning_codes

    claim_response = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={
            "edited_bullet": "Built a patent-pending service that supported 100 customers.",
            "status": "accepted",
        },
        headers=USER_A_HEADERS,
    )

    assert claim_response.status_code == 422
    claim_warning_codes = {
        warning["code"] for warning in claim_response.json()["detail"]["warnings"]
    }
    assert "draft_bullet_has_unsupported_claim" in claim_warning_codes


def test_tailored_resume_requires_accepted_bullets_before_export(client, sample_resume_text):
    application_id, _report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )

    response = client.post(
        f"/applications/{application_id}/tailored-resume/docx",
        headers=USER_A_HEADERS,
    )

    assert response.status_code == 422
    assert (
        response.json()["detail"] == "Accept at least one evidence-backed bullet before exporting."
    )


def test_tailored_resume_reset_restores_the_suggested_bullet(client, sample_resume_text):
    application_id, _report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )
    first_item = client.get(
        f"/applications/{application_id}/tailored-resume",
        headers=USER_A_HEADERS,
    ).json()["items"][0]

    edit_response = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={"edited_bullet": first_item["suggested_bullet"]},
        headers=USER_A_HEADERS,
    )

    assert edit_response.status_code == 200
    assert edit_response.json()["items"][0]["edited_bullet"] == first_item["suggested_bullet"]

    reset_response = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={"reset_edited_bullet": True},
        headers=USER_A_HEADERS,
    )

    assert reset_response.status_code == 200
    assert reset_response.json()["items"][0]["edited_bullet"] is None

    conflicting_response = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={"edited_bullet": first_item["suggested_bullet"], "reset_edited_bullet": True},
        headers=USER_A_HEADERS,
    )

    assert conflicting_response.status_code == 422


def test_tailored_resume_draft_is_recreated_after_reanalysis(client, sample_resume_text):
    application_id, first_report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )
    first_draft = client.get(
        f"/applications/{application_id}/tailored-resume",
        headers=USER_A_HEADERS,
    ).json()
    first_item = first_draft["items"][0]
    accepted_response = client.patch(
        f"/applications/{application_id}/tailored-resume/items/{first_item['id']}",
        json={"status": "accepted"},
        headers=USER_A_HEADERS,
    )
    assert accepted_response.status_code == 200

    application = _application(client, application_id, headers=USER_A_HEADERS)
    second_report_id = _analyze_application(
        client,
        application_id=application_id,
        resume_id=application["resume_id"],
        headers=USER_A_HEADERS,
    )
    recreated_draft = client.get(
        f"/applications/{application_id}/tailored-resume",
        headers=USER_A_HEADERS,
    ).json()

    assert second_report_id != first_report_id
    assert recreated_draft["report_id"] == second_report_id
    assert recreated_draft["accepted_count"] == 0
    assert all(item["status"] == "pending" for item in recreated_draft["items"])
    with client.app.state.session_factory() as db:
        drafts = list(db.scalars(select(TailoredResumeDraftRecord)))
    assert len(drafts) == 1
    assert drafts[0].report_id == second_report_id


def test_deleting_report_removes_draft_and_detaches_application_references(
    client, sample_resume_text
):
    application_id, report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )
    assert (
        client.get(
            f"/applications/{application_id}/tailored-resume",
            headers=USER_A_HEADERS,
        ).status_code
        == 200
    )

    delete_response = client.delete(f"/reports/{report_id}", headers=USER_A_HEADERS)

    assert delete_response.status_code == 200
    application = _application(client, application_id, headers=USER_A_HEADERS)
    assert application["status"] == "reviewed"
    assert application["analysis_id"] is None
    assert application["report_id"] is None
    assert application["job_id"] is None
    assert application["match_score"] is None
    assert application["resume_id"] is not None
    assert (
        client.get(
            f"/applications/{application_id}/tailored-resume",
            headers=USER_A_HEADERS,
        ).status_code
        == 422
    )
    with client.app.state.session_factory() as db:
        assert list(db.scalars(select(TailoredResumeDraftRecord))) == []


def test_deleting_resume_removes_draft_and_detaches_application_references(
    client, sample_resume_text
):
    application_id, _report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )
    application_before_delete = _application(client, application_id, headers=USER_A_HEADERS)
    assert (
        client.get(
            f"/applications/{application_id}/tailored-resume",
            headers=USER_A_HEADERS,
        ).status_code
        == 200
    )

    delete_response = client.delete(
        f"/resumes/{application_before_delete['resume_id']}",
        headers=USER_A_HEADERS,
    )

    assert delete_response.status_code == 200
    application = _application(client, application_id, headers=USER_A_HEADERS)
    assert application["status"] == "reviewed"
    assert application["resume_id"] is None
    assert application["job_id"] is None
    assert application["analysis_id"] is None
    assert application["report_id"] is None
    assert application["match_score"] is None
    with client.app.state.session_factory() as db:
        assert list(db.scalars(select(TailoredResumeDraftRecord))) == []


def test_tailored_resume_draft_is_tenant_scoped(client, sample_resume_text):
    application_id, _report_id = _create_analyzed_application(
        client, sample_resume_text, headers=USER_A_HEADERS
    )

    response = client.get(
        f"/applications/{application_id}/tailored-resume",
        headers=USER_B_HEADERS,
    )

    assert response.status_code == 404


def test_sqlite_engine_enforces_foreign_key_constraints(client):
    with client.app.state.engine.connect() as connection:
        assert connection.exec_driver_sql("PRAGMA foreign_keys").scalar_one() == 1


def _create_analyzed_application(
    client,
    resume_text: str,
    *,
    headers: dict[str, str],
    reviewed_profile: dict | None = None,
) -> tuple[int, int]:
    resume_id = _upload_resume(client, resume_text, headers=headers)
    reviewed_profile = reviewed_profile or _reviewed_job_profile()

    draft_response = client.post(
        "/applications",
        json={
            "source_type": "url",
            "job_url": "https://example.com/jobs/tailored-backend-engineer",
            "reviewed_job_text": _reviewed_job_text(),
            "reviewed_job_profile": reviewed_profile,
            "resume_id": resume_id,
        },
        headers=headers,
    )
    assert draft_response.status_code == 201
    application_id = draft_response.json()["id"]

    report_id = _analyze_application(
        client,
        application_id=application_id,
        resume_id=resume_id,
        headers=headers,
    )
    return application_id, report_id


def _analyze_application(
    client,
    *,
    application_id: int,
    resume_id: int,
    headers: dict[str, str],
) -> int:
    analysis = successful_analysis(
        client,
        {
            "application_id": application_id,
            "resume_id": resume_id,
        },
        headers=headers,
    )
    return analysis["report_id"]


def _application(client, application_id: int, *, headers: dict[str, str]) -> dict:
    applications = client.get("/applications", headers=headers).json()["items"]
    return next(application for application in applications if application["id"] == application_id)


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
        "keywords": ["Python", "FastAPI", "SQL", "REST API"],
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
            {
                "confidence": "high",
                "evidence_text": "Build REST APIs for hiring workflows.",
                "id": "job_required_004",
                "importance": "required",
                "name": "REST API",
            },
        ],
        "responsibilities": ["Build REST APIs for hiring workflows."],
        "role_title": "Backend Engineer",
        "unclear_items": [],
        "warnings": [],
    }


def _reviewed_job_text() -> str:
    return """Role: Backend Engineer
Company: NovaHire AI

Responsibilities:
- Build REST APIs for hiring workflows.

Requirements:
- Required Python experience.
- Required FastAPI experience.
- Required SQL database experience.

Experience: 0-2 years.
"""

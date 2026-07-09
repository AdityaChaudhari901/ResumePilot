from io import BytesIO
from zipfile import ZipFile

import pytest
from sqlalchemy import select

from app.db.models import UserRecord
from app.schemas.agent import (
    AgentStepName,
    AgentTokenUsage,
    AgentWorkflowMode,
    CoverLetterAgentOutput,
    InterviewCoachAgentOutput,
    ResumeMatchAgentOutput,
)
from app.schemas.report import InterviewQuestionGroup
from app.services.crewai_workflow import CrewAIWorkflowSections, CrewAIWorkflowUnavailable
from app.services.pdf_resume_compiler import PdfCompilerUnavailable


def test_job_preview_parses_public_url_without_creating_report(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: _FakeJobFetchResponse(
            text="""<html><body>
            <h1>Backend Engineer</h1>
            <p>Company: NovaHire AI</p>
            <h2>Requirements</h2>
            <p>Required Python experience.</p>
            <p>Required FastAPI experience.</p>
            <p>Preferred Pytest experience.</p>
            <h2>Responsibilities</h2>
            <p>Build REST APIs for hiring workflows.</p>
            </body></html>"""
        ),
    )

    response = client.post(
        "/jobs/preview",
        json={"job_url": "https://example.com/jobs/backend-engineer"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["profile"]["role_title"] == "Backend Engineer"
    assert body["profile"]["company"] == "NovaHire AI"
    assert {skill["name"] for skill in body["profile"]["required_skills"]} >= {
        "Python",
        "FastAPI",
    }
    assert {skill["name"] for skill in body["profile"]["preferred_skills"]} >= {"Pytest"}
    assert body["raw_text_char_count"] > 40

    history_response = client.get("/reports")
    assert history_response.status_code == 200
    assert history_response.json()["items"] == []


def test_job_preview_marks_unclear_requirements_for_review(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: _FakeJobFetchResponse(
            text="""<html><body>
            <h1>Persistent Careers</h1>
            <p>Join our engineering team and collaborate with product teams.</p>
            <p>This public page describes culture but exposes no explicit skill requirements.</p>
            </body></html>"""
        ),
    )

    response = client.post(
        "/jobs/preview",
        json={"job_url": "https://example.com/jobs/unclear"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing_requirements"
    assert body["profile"]["required_skills"] == []
    assert "required_skills_unclear" in {warning["code"] for warning in body["profile"]["warnings"]}
    assert any(check["code"] == "required_or_preferred_skills" for check in body["quality_checks"])


def test_analyze_uses_reviewed_job_profile_without_refetching(
    client, monkeypatch, sample_resume_text
):
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
    )
    assert upload_response.status_code == 201
    resume_id = upload_response.json()["resume_id"]

    def fail_fetch(*args, **kwargs):
        raise AssertionError("analysis should use reviewed_job_profile instead of refetching")

    monkeypatch.setattr("app.services.analysis_service.fetch_job_text", fail_fetch)

    analyze_response = client.post(
        "/jobs/analyze",
        json={
            "resume_id": resume_id,
            "job_url": "https://example.com/jobs/reviewed",
            "reviewed_job_profile": {
                "benefits": [],
                "company": "Reviewed Labs",
                "employment_type": None,
                "experience_level": "0-2 years",
                "job_id": 0,
                "keywords": ["Python", "FastAPI"],
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
                ],
                "responsibilities": ["Build REST APIs for reviewed workflows."],
                "role_title": "Reviewed Backend Engineer",
                "unclear_items": [],
                "warnings": [],
            },
        },
    )

    assert analyze_response.status_code == 200
    body = analyze_response.json()

    report_response = client.get(f"/reports/{body['report_id']}")
    assert report_response.status_code == 200
    report = report_response.json()
    assert {skill["skill"] for skill in report["matched_skills"]} >= {"Python", "FastAPI"}

    history_response = client.get("/reports")
    assert history_response.status_code == 200
    item = history_response.json()["items"][0]
    assert item["company"] == "Reviewed Labs"
    assert item["role"] == "Reviewed Backend Engineer"


def test_upload_analyze_and_read_report(client, sample_resume_text, sample_job_text):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    assert body["status"] == "completed"
    assert body["match_score"] >= 70

    history_response = client.get("/reports")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history["items"]) == 1
    history_item = history["items"][0]
    assert history_item["report_id"] == body["report_id"]
    assert history_item["analysis_id"] == body["analysis_id"]
    assert history_item["resume_id"] == body["resume_id"]
    assert history_item["company"] == "NovaHire AI"
    assert history_item["role"] == "Junior Backend Engineer"
    assert history_item["resume_candidate_name"] == "Aarav Sharma"
    assert history_item["matched_skills_count"] >= 1
    assert history_item["created_at"]

    resume_response = client.get(f"/resumes/{body['resume_id']}")
    assert resume_response.status_code == 200
    resume = resume_response.json()
    assert resume["resume_id"] == body["resume_id"]
    assert resume["candidate"]["name"] == "Aarav Sharma"
    assert resume["skills"]
    assert resume["facts"]

    report_response = client.get(f"/reports/{body['report_id']}")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["analysis_id"] == body["analysis_id"]
    assert report["tailored_bullets"]
    assert all(item["evidence_ids"] for item in report["tailored_bullets"])

    markdown_response = client.get(f"/reports/{body['report_id']}/markdown")
    assert markdown_response.status_code == 200
    assert "# Job Fit Report" in markdown_response.text

    latex_response = client.get(f"/reports/{body['report_id']}/resume/latex")
    assert latex_response.status_code == 200
    assert latex_response.headers["content-type"].startswith("application/x-tex")
    assert (
        latex_response.headers["content-disposition"]
        == f'attachment; filename="resumepilot-report-{body["report_id"]}.tex"'
    )
    assert r"\documentclass[letterpaper,10pt]{article}" in latex_response.text
    assert r"\section{Evidence-Backed Tailored Highlights}" in latex_response.text
    assert "Python" in latex_response.text
    assert "Docker" not in latex_response.text

    docx_response = client.get(f"/reports/{body['report_id']}/resume/docx")
    assert docx_response.status_code == 200
    assert docx_response.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert (
        docx_response.headers["content-disposition"]
        == f'attachment; filename="resumepilot-report-{body["report_id"]}.docx"'
    )
    assert docx_response.content.startswith(b"PK")
    with ZipFile(BytesIO(docx_response.content)) as archive:
        assert "word/document.xml" in archive.namelist()

    trace_response = client.get(f"/reports/{body['report_id']}/trace")
    assert trace_response.status_code == 200
    trace_body = trace_response.json()
    assert trace_body["analysis_id"] == body["analysis_id"]
    assert trace_body["report_id"] == body["report_id"]
    assert trace_body["trace"]["mode"] == AgentWorkflowMode.deterministic_fallback
    assert [step["name"] for step in trace_body["trace"]["steps"]] == [
        AgentStepName.jd_parser,
        AgentStepName.resume_match,
        AgentStepName.ats_optimizer,
        AgentStepName.cover_letter,
        AgentStepName.interview_coach,
        AgentStepName.validation_gate,
    ]
    assert isinstance(trace_body["trace"]["duration_ms"], int)
    assert all(isinstance(step["duration_ms"], int) for step in trace_body["trace"]["steps"])
    assert trace_body["trace"]["provider"] is None
    assert trace_body["trace"]["model"] is None
    assert trace_body["trace"]["token_usage"] is None
    assert trace_body["trace"]["cost_estimate_usd"] is None
    assert trace_body["trace"]["runtime_metadata"] == {}


def test_read_tailored_resume_pdf_download(
    client, monkeypatch, sample_resume_text, sample_job_text, settings
):
    def fake_compile_latex_to_pdf(
        latex_source: str,
        *,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> bytes:
        assert r"\documentclass[letterpaper,10pt]{article}" in latex_source
        assert timeout_seconds == settings.latex_compile_timeout_seconds
        assert max_output_bytes == settings.latex_pdf_max_bytes
        return b"%PDF-1.7\n% ResumePilot test PDF\n"

    monkeypatch.setattr(
        "app.services.analysis_service.compile_latex_to_pdf",
        fake_compile_latex_to_pdf,
    )
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)

    pdf_response = client.get(f"/reports/{body['report_id']}/resume/pdf")

    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"].startswith("application/pdf")
    assert (
        pdf_response.headers["content-disposition"]
        == f'attachment; filename="resumepilot-report-{body["report_id"]}.pdf"'
    )
    assert pdf_response.content.startswith(b"%PDF-1.7")


def test_read_tailored_resume_pdf_reports_missing_compiler(
    client, monkeypatch, sample_resume_text, sample_job_text
):
    def fake_compile_latex_to_pdf(
        _latex_source: str,
        *,
        timeout_seconds: int,
        max_output_bytes: int,
    ) -> bytes:
        raise PdfCompilerUnavailable("No compiler installed.")

    monkeypatch.setattr(
        "app.services.analysis_service.compile_latex_to_pdf",
        fake_compile_latex_to_pdf,
    )
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)

    pdf_response = client.get(f"/reports/{body['report_id']}/resume/pdf")

    assert pdf_response.status_code == 503
    assert (
        pdf_response.json()["detail"] == "PDF export requires tectonic or pdflatex on the server."
    )


def test_crewai_fallback_trace_is_persisted(
    client, monkeypatch, sample_resume_text, sample_job_text, settings
):
    settings.agent_workflow_mode = AgentWorkflowMode.crewai

    def unavailable_runner(_settings):
        raise CrewAIWorkflowUnavailable("CrewAI runtime unavailable in API test")

    monkeypatch.setattr(
        "app.services.agent_workflow.build_crewai_workflow_runner",
        unavailable_runner,
    )

    body = _upload_and_analyze(client, sample_resume_text, sample_job_text, plan="premium")

    report_response = client.get(f"/reports/{body['report_id']}")
    assert report_response.status_code == 200
    warning_codes = [warning["code"] for warning in report_response.json()["validation_warnings"]]
    assert "crewai_unavailable" in warning_codes

    trace_response = client.get(f"/reports/{body['report_id']}/trace")
    assert trace_response.status_code == 200
    trace = trace_response.json()["trace"]
    assert trace["mode"] == AgentWorkflowMode.deterministic_fallback
    assert trace["steps"][0]["name"] == AgentStepName.crewai_runtime
    assert trace["steps"][0]["status"] == "failed"
    assert isinstance(trace["steps"][0]["duration_ms"], int)
    assert isinstance(trace["duration_ms"], int)
    assert trace["provider"] == "vertex"
    assert trace["model"] == "google/gemini-3.5-flash"
    assert trace["token_usage"] is None
    assert trace["cost_estimate_usd"] is None
    assert trace["runtime_metadata"]["runtime_status"] == "failed"
    assert "crewai_unavailable" in trace["validation_warning_codes"]


def test_crewai_success_trace_is_persisted(
    client, monkeypatch, sample_resume_text, sample_job_text, settings
):
    settings.agent_workflow_mode = AgentWorkflowMode.crewai

    class FakeCrewAIRunner:
        def run(self, **kwargs):
            match = kwargs["match"]
            evidence_ids = match.matched_skills[0].resume_evidence_ids
            return CrewAIWorkflowSections(
                resume_match=ResumeMatchAgentOutput(
                    summary="CrewAI-reviewed fit persisted through the API.",
                    strongest_matches=["Python", "FastAPI"],
                    weak_areas=[],
                    recommended_positioning="Lead with backend API evidence.",
                    evidence_ids=evidence_ids,
                    confidence=match.confidence,
                ),
                cover_letter=CoverLetterAgentOutput(
                    draft=(
                        "Dear Hiring Team,\n\n"
                        "I am interested in this backend role and would lead with validated "
                        "Python and FastAPI evidence.\n\n"
                        "Confidence note: this draft uses only validated resume evidence.\n\n"
                        "Sincerely,\nAarav Sharma"
                    ),
                    confidence_note=(
                        "Confidence note: this draft uses only validated resume evidence."
                    ),
                    evidence_ids=evidence_ids,
                ),
                interview_coach=InterviewCoachAgentOutput(
                    question_groups=[
                        InterviewQuestionGroup(
                            category="Technical",
                            questions=["How did you structure the FastAPI backend?"],
                            suggested_answer_evidence_ids=evidence_ids,
                        )
                    ]
                ),
                token_usage=AgentTokenUsage(
                    total_tokens=321,
                    prompt_tokens=250,
                    completion_tokens=71,
                    successful_requests=3,
                ),
            )

    monkeypatch.setattr(
        "app.services.agent_workflow.build_crewai_workflow_runner",
        lambda _settings: FakeCrewAIRunner(),
    )

    body = _upload_and_analyze(client, sample_resume_text, sample_job_text, plan="premium")

    report_response = client.get(f"/reports/{body['report_id']}")
    assert report_response.status_code == 200
    assert report_response.json()["executive_summary"].startswith("CrewAI-reviewed fit")

    trace_response = client.get(f"/reports/{body['report_id']}/trace")
    assert trace_response.status_code == 200
    trace = trace_response.json()["trace"]
    assert trace["mode"] == AgentWorkflowMode.crewai
    runtime_step = next(
        step for step in trace["steps"] if step["name"] == AgentStepName.crewai_runtime
    )
    assert runtime_step["status"] == "completed"
    assert isinstance(runtime_step["duration_ms"], int)
    assert isinstance(trace["duration_ms"], int)
    assert trace["provider"] == "vertex"
    assert trace["model"] == "google/gemini-3.5-flash"
    assert trace["token_usage"]["total_tokens"] == 321
    assert trace["token_usage"]["prompt_tokens"] == 250
    assert trace["token_usage"]["completion_tokens"] == 71
    assert trace["token_usage"]["successful_requests"] == 3
    assert trace["cost_estimate_usd"] == pytest.approx(0.001014)
    assert trace["runtime_metadata"]["runtime_status"] == "completed"
    assert trace["runtime_metadata"]["cost_estimate_source"] == "provider_pricing_config"
    assert trace["runtime_metadata"]["pricing_version"] == "2026-07-08.vertex-global-standard.v1"
    assert trace["runtime_metadata"]["billable_input_tokens"] == 250
    assert trace["runtime_metadata"]["billable_output_tokens"] == 71
    assert "crewai_unavailable" not in trace["validation_warning_codes"]

    usage_response = client.get("/usage/summary")
    assert usage_response.status_code == 200
    usage = usage_response.json()
    assert usage["plan"] == "premium"
    assert usage["live_crewai_enabled"] is True
    crewai_limit = next(item for item in usage["limits"] if item["metric"] == "crewai_runs")
    assert crewai_limit["used"] == 1
    assert crewai_limit["limit"] == 100
    assert usage["total_cost_estimate_usd"] == pytest.approx(0.001014)


def _upload_and_analyze(
    client,
    resume_text: str,
    job_text: str,
    *,
    plan: str = "free",
) -> dict:
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
    )

    assert upload_response.status_code == 201
    resume_id = upload_response.json()["resume_id"]
    if plan != "free":
        _set_dev_user_plan(client, plan)

    analyze_response = client.post(
        "/jobs/analyze",
        json={"resume_id": resume_id, "job_text": job_text},
    )

    assert analyze_response.status_code == 200
    body = analyze_response.json()
    body["resume_id"] = resume_id
    return body


def _set_dev_user_plan(client, plan: str) -> None:
    with client.app.state.session_factory() as db:
        user = db.scalar(
            select(UserRecord).where(UserRecord.external_id == "local-dev-user").limit(1)
        )
        assert user is not None
        user.plan = plan
        user.subscription_status = "active"
        db.commit()


class _FakeJobFetchResponse:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text

    def raise_for_status(self) -> None:
        return None

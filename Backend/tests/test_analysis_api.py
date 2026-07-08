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


def test_upload_analyze_and_read_report(client, sample_resume_text, sample_job_text):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    assert body["status"] == "completed"
    assert body["match_score"] >= 70

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

    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)

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

    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)

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
    assert trace["cost_estimate_usd"] is None
    assert trace["runtime_metadata"]["runtime_status"] == "completed"
    assert "crewai_unavailable" not in trace["validation_warning_codes"]


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
    return analyze_response.json()

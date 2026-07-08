import pytest

from app.schemas.agent import (
    AgentStepName,
    AgentTokenUsage,
    AgentWorkflowMode,
    AgentWorkflowTrace,
    CoverLetterAgentOutput,
    InterviewCoachAgentOutput,
    ResumeMatchAgentOutput,
)
from app.schemas.report import InterviewQuestionGroup
from app.services.agent_workflow import run_application_agent_workflow
from app.services.crewai_workflow import CrewAIWorkflowSections, CrewAIWorkflowUnavailable
from app.services.job_parser import parse_job_profile
from app.services.matcher import match_resume_to_job
from app.services.resume_parser import parse_resume_profile


def test_agent_workflow_generates_validated_report_sections(sample_resume_text, sample_job_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)

    result = run_application_agent_workflow(analysis_id=1, resume=resume, job=job, match=match)

    assert result.trace.mode == AgentWorkflowMode.deterministic_fallback
    assert [step.name for step in result.trace.steps] == [
        AgentStepName.jd_parser,
        AgentStepName.resume_match,
        AgentStepName.ats_optimizer,
        AgentStepName.cover_letter,
        AgentStepName.interview_coach,
        AgentStepName.validation_gate,
    ]
    assert "Recommended positioning" in result.report.executive_summary
    assert "Confidence note:" in result.report.cover_letter
    assert {group.category for group in result.report.interview_questions} >= {
        "Technical",
        "Behavioral",
        "Project Deep Dive",
        "Gap-Focused",
    }
    assert all(bullet.evidence_ids for bullet in result.report.tailored_bullets)
    assert "cover_letter_has_unsupported_skill" not in result.trace.validation_warning_codes
    assert isinstance(result.trace.duration_ms, int)
    assert result.trace.duration_ms >= 0
    assert all(isinstance(step.duration_ms, int) for step in result.trace.steps)
    assert all(step.duration_ms >= 0 for step in result.trace.steps if step.duration_ms is not None)
    assert result.trace.provider is None
    assert result.trace.model is None
    assert result.trace.token_usage is None
    assert result.trace.cost_estimate_usd is None
    assert result.trace.runtime_metadata == {}


def test_agent_workflow_trace_accepts_legacy_payload_without_timings():
    trace = AgentWorkflowTrace.model_validate(
        {
            "mode": "deterministic_fallback",
            "steps": [
                {
                    "name": "validation_gate",
                    "status": "degraded",
                    "summary": "Legacy trace without timing fields.",
                }
            ],
            "validation_warning_codes": [],
        }
    )

    assert trace.duration_ms is None
    assert trace.steps[0].duration_ms is None
    assert trace.provider is None
    assert trace.model is None
    assert trace.token_usage is None
    assert trace.cost_estimate_usd is None
    assert trace.runtime_metadata == {}


def test_crewai_mode_falls_back_when_runtime_is_unavailable(
    monkeypatch,
    sample_resume_text,
    sample_job_text,
    settings,
):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    crewai_settings = settings.model_copy(update={"agent_workflow_mode": AgentWorkflowMode.crewai})

    def unavailable_runner(_settings):
        raise CrewAIWorkflowUnavailable("CrewAI runtime unavailable in test")

    monkeypatch.setattr(
        "app.services.agent_workflow.build_crewai_workflow_runner",
        unavailable_runner,
    )

    result = run_application_agent_workflow(
        analysis_id=1,
        resume=resume,
        job=job,
        match=match,
        settings=crewai_settings,
    )

    assert result.trace.mode == AgentWorkflowMode.deterministic_fallback
    assert result.trace.steps[0].name == AgentStepName.crewai_runtime
    assert result.trace.steps[0].status == "failed"
    assert isinstance(result.trace.steps[0].duration_ms, int)
    assert isinstance(result.trace.duration_ms, int)
    assert result.trace.provider == "vertex"
    assert result.trace.model == "google/gemini-3.5-flash"
    assert result.trace.token_usage is None
    assert result.trace.runtime_metadata["runtime_status"] == "failed"
    assert result.trace.runtime_metadata["token_usage_source"] == "unavailable"
    assert result.trace.runtime_metadata["cost_estimate_source"] == "unavailable"
    assert "crewai_unavailable" in result.trace.validation_warning_codes


def test_crewai_mode_uses_live_sections_then_validates(
    monkeypatch,
    sample_resume_text,
    sample_job_text,
    settings,
):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    crewai_settings = settings.model_copy(update={"agent_workflow_mode": AgentWorkflowMode.crewai})
    evidence_ids = match.matched_skills[0].resume_evidence_ids

    class FakeCrewAIRunner:
        def run(self, **_kwargs):
            return CrewAIWorkflowSections(
                resume_match=ResumeMatchAgentOutput(
                    summary="CrewAI-reviewed fit: strong Python and FastAPI evidence.",
                    strongest_matches=["Python", "FastAPI"],
                    weak_areas=[],
                    recommended_positioning=(
                        "Lead with backend API evidence and be direct about Docker preparation."
                    ),
                    evidence_ids=evidence_ids,
                    confidence=match.confidence,
                ),
                cover_letter=CoverLetterAgentOutput(
                    draft=(
                        "Dear Hiring Team,\n\n"
                        "I am interested in Junior Backend Engineer at NovaHire AI. "
                        "My resume shows supported Python and FastAPI project evidence, "
                        "and I would position the application around those backend strengths.\n\n"
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
                        ),
                        InterviewQuestionGroup(
                            category="Behavioral",
                            questions=["How do you improve backend reliability?"],
                            suggested_answer_evidence_ids=evidence_ids,
                        ),
                    ]
                ),
                step_durations_ms={
                    AgentStepName.resume_match.value: 11,
                    AgentStepName.cover_letter.value: 22,
                    AgentStepName.interview_coach.value: 33,
                },
                token_usage=AgentTokenUsage(
                    total_tokens=123,
                    prompt_tokens=90,
                    completion_tokens=33,
                    successful_requests=3,
                ),
            )

    monkeypatch.setattr(
        "app.services.agent_workflow.build_crewai_workflow_runner",
        lambda _settings: FakeCrewAIRunner(),
    )

    result = run_application_agent_workflow(
        analysis_id=1,
        resume=resume,
        job=job,
        match=match,
        settings=crewai_settings,
    )

    assert result.trace.mode == AgentWorkflowMode.crewai
    assert result.trace.steps[1].name == AgentStepName.crewai_runtime
    assert result.trace.steps[1].status == "completed"
    assert isinstance(result.trace.duration_ms, int)
    assert all(step.duration_ms is not None for step in result.trace.steps)
    assert result.trace.provider == "vertex"
    assert result.trace.model == "google/gemini-3.5-flash"
    assert result.trace.token_usage is not None
    assert result.trace.token_usage.total_tokens == 123
    assert result.trace.token_usage.successful_requests == 3
    assert result.trace.cost_estimate_usd == pytest.approx(0.000432)
    assert result.trace.runtime_metadata["runtime_status"] == "completed"
    assert result.trace.runtime_metadata["token_usage_source"] == "crewai_llm_summary"
    assert result.trace.runtime_metadata["cost_estimate_source"] == "provider_pricing_config"
    assert result.trace.runtime_metadata["pricing_version"] == (
        "2026-07-08.vertex-global-standard.v1"
    )
    assert result.trace.runtime_metadata["pricing_source_url"] == (
        "https://cloud.google.com/gemini-enterprise-agent-platform/generative-ai/pricing"
    )
    assert result.trace.runtime_metadata["billable_input_tokens"] == 90
    assert result.trace.runtime_metadata["billable_output_tokens"] == 33
    assert result.report.executive_summary.startswith("CrewAI-reviewed fit")
    assert "validated resume evidence" in result.report.cover_letter
    assert "crewai_unavailable" not in result.trace.validation_warning_codes

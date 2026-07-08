from app.schemas.agent import (
    AgentStepName,
    AgentWorkflowMode,
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
    assert result.report.executive_summary.startswith("CrewAI-reviewed fit")
    assert "validated resume evidence" in result.report.cover_letter
    assert "crewai_unavailable" not in result.trace.validation_warning_codes

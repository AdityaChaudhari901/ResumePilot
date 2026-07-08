from app.schemas.agent import AgentStepName, AgentWorkflowMode
from app.services.agent_workflow import run_application_agent_workflow
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

from app.schemas.agent import (
    AgentStepName,
    AgentTokenUsage,
    AgentWorkflowMode,
    AgentWorkflowTrace,
    CoverLetterAgentOutput,
    InterviewCoachAgentOutput,
    LiveDraftSections,
    ResumeMatchAgentOutput,
)
from app.schemas.common import ValidationSeverity
from app.schemas.operation import LiveDraftProposal
from app.schemas.report import InterviewQuestionGroup
from app.services.agent_workflow import (
    apply_approved_live_draft,
    run_application_agent_workflow,
    with_langgraph_fallback_warning,
    with_rejected_live_draft,
)
from app.services.job_parser import parse_job_profile
from app.services.matcher import match_resume_to_job
from app.services.report_generator import report_to_markdown
from app.services.resume_parser import parse_resume_profile


def test_agent_workflow_generates_validated_report_sections(sample_resume_text, sample_job_text):
    resume, job, match, result = _deterministic_context(sample_resume_text, sample_job_text)

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
    assert result.trace.provider is None
    assert result.trace.model is None
    assert result.trace.token_usage is None
    assert result.trace.cost_estimate_usd is None
    assert result.trace.runtime_metadata == {}
    assert result.report.cover_letter_evidence_ids
    assert result.report.validation_status == result.trace.validation_status
    assert resume.resume_id == 1
    assert job.job_id == 1
    assert match.matched_skills


def test_agent_workflow_trace_accepts_legacy_crewai_payload_without_timings():
    trace = AgentWorkflowTrace.model_validate(
        {
            "mode": "crewai",
            "steps": [
                {
                    "name": "crewai_runtime",
                    "status": "completed",
                    "summary": "Historical CrewAI trace retained for report compatibility.",
                }
            ],
            "validation_warning_codes": [],
        }
    )

    assert trace.mode == AgentWorkflowMode.crewai
    assert trace.steps[0].name == AgentStepName.crewai_runtime
    assert trace.duration_ms is None
    assert trace.steps[0].duration_ms is None
    assert trace.validation_status == ValidationSeverity.pass_


def test_langgraph_unavailable_records_safe_deterministic_fallback(
    settings,
    sample_resume_text,
    sample_job_text,
):
    _resume, _job, _match, deterministic = _deterministic_context(
        sample_resume_text, sample_job_text
    )
    settings.agent_workflow_mode = AgentWorkflowMode.langgraph

    result = with_langgraph_fallback_warning(
        deterministic,
        RuntimeError("private provider error"),
        settings=settings,
        live_duration_ms=7,
    )

    assert result.trace.mode == AgentWorkflowMode.deterministic_fallback
    assert result.trace.steps[0].name == AgentStepName.langgraph_runtime
    assert result.trace.steps[0].status == "failed"
    assert result.trace.steps[0].duration_ms == 7
    assert result.trace.provider == "vertex"
    assert result.trace.model == "google_genai/gemini-3.5-flash"
    assert result.trace.runtime_metadata["workflow_runtime"] == "langgraph"
    assert result.trace.runtime_metadata["runtime_status"] == "failed"
    assert "langgraph_unavailable" in result.trace.validation_warning_codes
    assert "private provider error" not in result.report.model_dump_json()


def test_approved_langgraph_sections_are_applied_after_validation(
    settings,
    sample_resume_text,
    sample_job_text,
):
    resume, job, match, deterministic = _deterministic_context(sample_resume_text, sample_job_text)
    sections = _safe_live_sections(match)
    proposal = _proposal_for_sections(sections)

    result = apply_approved_live_draft(
        resume=resume,
        job=job,
        match=match,
        deterministic_result=deterministic,
        settings=settings,
        sections=sections,
        proposal=proposal,
        live_duration_ms=42,
    )

    assert result.trace.mode == AgentWorkflowMode.langgraph
    assert result.report.executive_summary.startswith(
        "The deterministic match is supported by linked resume evidence."
    )
    assert result.report.cover_letter == sections.cover_letter.draft
    assert result.report.cover_letter_evidence_ids == sections.cover_letter.evidence_ids
    assert result.trace.token_usage == sections.token_usage
    assert result.trace.runtime_metadata["token_usage_source"] == "langchain_message_usage"
    assert result.trace.steps[-1].name == AgentStepName.human_approval
    assert result.trace.steps[-1].status == "completed"
    assert result.report.validation_status != ValidationSeverity.block


def test_rejected_langgraph_sections_keep_deterministic_report(
    settings,
    sample_resume_text,
    sample_job_text,
):
    _resume, _job, match, deterministic = _deterministic_context(
        sample_resume_text, sample_job_text
    )
    sections = _safe_live_sections(match)

    result = with_rejected_live_draft(
        deterministic,
        settings=settings,
        sections=sections,
        live_duration_ms=19,
    )

    assert result.report == deterministic.report
    assert result.trace.mode == AgentWorkflowMode.deterministic_fallback
    assert result.trace.steps[0].name == AgentStepName.langgraph_runtime
    assert result.trace.steps[1].name == AgentStepName.human_approval
    assert result.trace.steps[1].status == "degraded"
    assert result.trace.runtime_metadata["runtime_status"] == "rejected"


def test_approved_langgraph_unsupported_claims_are_replaced_before_persistence(
    settings,
    sample_resume_text,
    sample_job_text,
):
    resume, job, match, deterministic = _deterministic_context(sample_resume_text, sample_job_text)
    evidence_ids = _evidence_ids(match)
    unsafe_sections = LiveDraftSections(
        resume_match=ResumeMatchAgentOutput(
            summary=(
                "Senior executive at Invented Corp who served 1,000,000 users with 99.99% uptime."
            ),
            strongest_matches=["Python"],
            weak_areas=[],
            recommended_positioning="Lead with this certified production record.",
            evidence_ids=evidence_ids,
            confidence=match.confidence,
        ),
        cover_letter=CoverLetterAgentOutput(
            draft=(
                "I worked at Imaginary Labs and drove 900% revenue growth through "
                "50 production deployments."
            ),
            confidence_note="Unverified live draft.",
            evidence_ids=evidence_ids,
        ),
        interview_coach=InterviewCoachAgentOutput(
            question_groups=[
                InterviewQuestionGroup(
                    category="Behavioral",
                    questions=["Describe the claimed executive record."],
                    suggested_answer_evidence_ids=["invented_001"],
                )
            ]
        ),
        token_usage=AgentTokenUsage(successful_requests=3),
    )
    candidate_name = resume.candidate.name
    assert candidate_name
    validated_proposal = LiveDraftProposal(
        executive_summary=deterministic.report.executive_summary.replace(
            candidate_name, "Candidate"
        ),
        cover_letter=deterministic.report.cover_letter.replace(candidate_name, "Candidate"),
        interview_questions=deterministic.report.interview_questions,
    )

    result = apply_approved_live_draft(
        resume=resume,
        job=job,
        match=match,
        deterministic_result=deterministic,
        settings=settings,
        sections=unsafe_sections,
        proposal=validated_proposal,
        live_duration_ms=12,
    )
    markdown = report_to_markdown(result.report)

    assert result.report.executive_summary == validated_proposal.executive_summary
    assert result.report.cover_letter == validated_proposal.cover_letter
    assert result.report.interview_questions == validated_proposal.interview_questions
    assert result.report.validation_status == ValidationSeverity.block
    assert set(result.trace.runtime_metadata["blocked_live_sections"].split(",")) == {
        AgentStepName.resume_match.value,
        AgentStepName.cover_letter.value,
        AgentStepName.interview_coach.value,
    }
    assert {warning.code for warning in result.report.validation_warnings} >= {
        "live_resume_match_blocked",
        "live_cover_letter_blocked",
        "live_interview_coach_blocked",
    }
    for unsafe_text in ("Invented Corp", "1,000,000", "Imaginary Labs", "900%"):
        assert unsafe_text not in result.report.model_dump_json()
        assert unsafe_text not in markdown


def _deterministic_context(resume_text: str, job_text: str):
    resume = parse_resume_profile(resume_text, resume_id=1)
    job = parse_job_profile(job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    result = run_application_agent_workflow(
        analysis_id=1,
        resume=resume,
        job=job,
        match=match,
    )
    return resume, job, match, result


def _safe_live_sections(match) -> LiveDraftSections:
    evidence_ids = _evidence_ids(match)
    return LiveDraftSections(
        resume_match=ResumeMatchAgentOutput(
            summary="The deterministic match is supported by linked resume evidence.",
            strongest_matches=[],
            weak_areas=[],
            recommended_positioning="Use linked evidence and describe gaps honestly.",
            evidence_ids=evidence_ids,
            confidence=match.confidence,
        ),
        cover_letter=CoverLetterAgentOutput(
            draft=(
                "Dear Hiring Team,\n\nThe linked resume evidence supports this application.\n\n"
                "Confidence note: review the validated evidence before use."
            ),
            confidence_note="Confidence note: review the validated evidence before use.",
            evidence_ids=evidence_ids,
        ),
        interview_coach=InterviewCoachAgentOutput(
            question_groups=[
                InterviewQuestionGroup(
                    category="Technical",
                    questions=["Which linked evidence best demonstrates the relevant work?"],
                    suggested_answer_evidence_ids=evidence_ids,
                )
            ]
        ),
        step_durations_ms={
            AgentStepName.resume_match.value: 10,
            AgentStepName.cover_letter.value: 20,
            AgentStepName.interview_coach.value: 30,
        },
        token_usage=AgentTokenUsage(
            total_tokens=123,
            prompt_tokens=90,
            completion_tokens=33,
            successful_requests=3,
        ),
    )


def _proposal_for_sections(sections: LiveDraftSections) -> LiveDraftProposal:
    return LiveDraftProposal(
        executive_summary=(
            f"{sections.resume_match.summary} Recommended positioning: "
            f"{sections.resume_match.recommended_positioning}"
        ),
        cover_letter=sections.cover_letter.draft,
        interview_questions=sections.interview_coach.question_groups,
    )


def _evidence_ids(match) -> list[str]:
    evidence_ids = [
        evidence_id for item in match.matched_skills for evidence_id in item.resume_evidence_ids
    ]
    assert evidence_ids
    return list(dict.fromkeys(evidence_ids))[:3]

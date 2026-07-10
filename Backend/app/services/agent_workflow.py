import re
from collections.abc import Callable
from dataclasses import dataclass
from time import perf_counter

from app.core.config import Settings
from app.schemas.agent import (
    AgentStepName,
    AgentStepTrace,
    AgentTokenUsage,
    AgentWorkflowMode,
    AgentWorkflowResult,
    AgentWorkflowTrace,
    AtsOptimizerAgentOutput,
    CoverLetterAgentOutput,
    InterviewCoachAgentOutput,
    LiveDraftSections,
    ResumeMatchAgentOutput,
)
from app.schemas.common import (
    Confidence,
    ValidationSeverity,
    ValidationWarning,
    validation_status_from_warnings,
)
from app.schemas.job import JobProfile
from app.schemas.match import MatchResult
from app.schemas.operation import LiveDraftProposal
from app.schemas.report import ApplicationReport, InterviewQuestionGroup
from app.schemas.resume import ResumeFact, ResumeProfile
from app.services.claim_validation import find_unsupported_claims
from app.services.provider_pricing import ProviderCostEstimate, estimate_provider_cost
from app.services.report_generator import generate_report
from app.services.skill_normalizer import find_skills
from app.services.validator import validate_report_against_resume


@dataclass(frozen=True, slots=True)
class ValidatedLiveSections:
    executive_summary: str
    cover_letter: str
    cover_letter_evidence_ids: list[str]
    interview_questions: list[InterviewQuestionGroup]
    warnings: list[ValidationWarning]
    blocked_sections: frozenset[str]


def run_application_agent_workflow(
    *,
    analysis_id: int,
    resume: ResumeProfile,
    job: JobProfile,
    match: MatchResult,
    settings: Settings | None = None,
) -> AgentWorkflowResult:
    """Build the deterministic source-of-truth report before optional live drafting."""

    del settings
    return _run_deterministic_application_agent_workflow(
        analysis_id=analysis_id,
        resume=resume,
        job=job,
        match=match,
    )


def _run_deterministic_application_agent_workflow(
    *,
    analysis_id: int,
    resume: ResumeProfile,
    job: JobProfile,
    match: MatchResult,
) -> AgentWorkflowResult:
    """Run the deterministic fallback workflow.

    This deterministic fallback mirrors the live drafting sequence while keeping
    deterministic parsing, matching, and validation as the source of truth.
    """

    workflow_start = perf_counter()
    base_report = generate_report(analysis_id=analysis_id, resume=resume, job=job, match=match)
    jd_step_start = perf_counter()
    traces = [
        _step_trace(
            name=AgentStepName.jd_parser,
            status="completed",
            summary=(
                "Used structured JobProfile produced by deterministic job parsing; "
                "no hidden requirements inferred."
            ),
            started_at=jd_step_start,
        )
    ]

    fit, duration_ms = _timed_call(lambda: _resume_match_agent(resume, job, match))
    traces.append(
        AgentStepTrace(
            name=AgentStepName.resume_match,
            status="completed",
            summary=f"Explained fit with {len(fit.evidence_ids)} resume evidence references.",
            duration_ms=duration_ms,
        )
    )

    ats, duration_ms = _timed_call(lambda: _ats_optimizer_agent(base_report, match))
    traces.append(
        AgentStepTrace(
            name=AgentStepName.ats_optimizer,
            status="completed",
            summary=(
                f"Prepared {len(ats.tailored_bullets)} bullet suggestions and "
                f"{len(ats.keyword_suggestions)} keyword suggestions."
            ),
            duration_ms=duration_ms,
        )
    )

    cover_letter, duration_ms = _timed_call(lambda: _cover_letter_agent(resume, job, match))
    traces.append(
        AgentStepTrace(
            name=AgentStepName.cover_letter,
            status="completed",
            summary=(
                "Drafted cover letter from matched resume evidence only; "
                f"{len(cover_letter.evidence_ids)} evidence references used."
            ),
            duration_ms=duration_ms,
        )
    )

    interview, duration_ms = _timed_call(lambda: _interview_coach_agent(resume, match))
    traces.append(
        AgentStepTrace(
            name=AgentStepName.interview_coach,
            status="completed",
            summary=f"Prepared {len(interview.question_groups)} interview question groups.",
            duration_ms=duration_ms,
        )
    )

    report = base_report.model_copy(
        update={
            "executive_summary": _build_executive_summary(fit),
            "tailored_bullets": ats.tailored_bullets,
            "ats_keywords": ats.keyword_suggestions,
            "cover_letter": cover_letter.draft,
            "cover_letter_evidence_ids": cover_letter.evidence_ids,
            "interview_questions": interview.question_groups,
            "next_actions": _next_actions(base_report, fit, ats),
        }
    )

    validation_step_start = perf_counter()
    validation_warnings = _dedupe_warnings(
        [*report.validation_warnings, *validate_report_against_resume(report, resume)]
    )
    validation_status = _set_report_validation(report, validation_warnings)
    traces.append(
        _step_trace(
            name=AgentStepName.validation_gate,
            status=_validation_step_status(validation_status),
            summary=_validation_summary(validation_status, validation_warnings),
            started_at=validation_step_start,
        )
    )

    return AgentWorkflowResult(
        report=report,
        trace=AgentWorkflowTrace(
            mode=AgentWorkflowMode.deterministic_fallback,
            steps=traces,
            validation_warning_codes=[warning.code for warning in validation_warnings],
            validation_status=validation_status,
            duration_ms=_elapsed_ms(workflow_start),
        ),
    )


def apply_approved_live_draft(
    *,
    resume: ResumeProfile,
    job: JobProfile,
    match: MatchResult,
    deterministic_result: AgentWorkflowResult,
    settings: Settings,
    sections: LiveDraftSections,
    proposal: LiveDraftProposal,
    live_duration_ms: int,
) -> AgentWorkflowResult:
    workflow_start = perf_counter()
    ats, ats_duration_ms = _timed_call(
        lambda: _ats_optimizer_agent(deterministic_result.report, match)
    )
    validated_live = validate_live_draft_sections(
        sections=sections,
        deterministic_report=deterministic_result.report,
        resume=resume,
        job=job,
    )
    report = deterministic_result.report.model_copy(
        deep=True,
        update={
            "executive_summary": proposal.executive_summary,
            "tailored_bullets": ats.tailored_bullets,
            "ats_keywords": ats.keyword_suggestions,
            "cover_letter": proposal.cover_letter,
            "cover_letter_evidence_ids": validated_live.cover_letter_evidence_ids,
            "interview_questions": proposal.interview_questions,
            "next_actions": _next_actions(deterministic_result.report, sections.resume_match, ats),
        },
    )
    validation_step_start = perf_counter()
    validation_warnings = _dedupe_warnings(
        [
            *report.validation_warnings,
            *validated_live.warnings,
            *validate_report_against_resume(report, resume),
        ]
    )
    validation_status = _set_report_validation(report, validation_warnings)
    provider = _runtime_provider(settings)
    model = _runtime_model(settings)
    cost_estimate = estimate_provider_cost(
        provider=provider,
        model=model,
        region=settings.vertex_region,
        token_usage=sections.token_usage,
    )

    traces = [
        AgentStepTrace(
            name=AgentStepName.jd_parser,
            status="completed",
            summary=(
                "Used structured JobProfile produced by deterministic job parsing; "
                "no hidden requirements inferred."
            ),
            duration_ms=_step_duration(
                deterministic_result.trace.steps,
                AgentStepName.jd_parser,
            ),
        ),
        AgentStepTrace(
            name=AgentStepName.langgraph_runtime,
            status="completed",
            summary=(
                "Executed LangChain structured model calls inside resumable LangGraph nodes "
                f"with model {settings.llm_model}."
            ),
            duration_ms=live_duration_ms,
        ),
        AgentStepTrace(
            name=AgentStepName.resume_match,
            status=(
                "degraded"
                if AgentStepName.resume_match.value in validated_live.blocked_sections
                else "completed"
            ),
            summary=(
                "Unsafe live resume-match text was replaced with deterministic content."
                if AgentStepName.resume_match.value in validated_live.blocked_sections
                else (
                    "Live AI explained deterministic fit with "
                    f"{len(sections.resume_match.evidence_ids)} resume evidence references."
                )
            ),
            duration_ms=sections.step_durations_ms.get(AgentStepName.resume_match.value),
        ),
        AgentStepTrace(
            name=AgentStepName.ats_optimizer,
            status="completed",
            summary=(
                "Kept ATS keyword and bullet suggestions deterministic so evidence IDs remain "
                "source-of-truth controlled."
            ),
            duration_ms=ats_duration_ms,
        ),
        AgentStepTrace(
            name=AgentStepName.cover_letter,
            status=(
                "degraded"
                if AgentStepName.cover_letter.value in validated_live.blocked_sections
                else "completed"
            ),
            summary=(
                "Unsafe live cover-letter text was replaced with deterministic content."
                if AgentStepName.cover_letter.value in validated_live.blocked_sections
                else (
                    "Live AI drafted the cover letter from validated evidence; "
                    f"{len(sections.cover_letter.evidence_ids)} evidence references used."
                )
            ),
            duration_ms=sections.step_durations_ms.get(AgentStepName.cover_letter.value),
        ),
        AgentStepTrace(
            name=AgentStepName.interview_coach,
            status=(
                "degraded"
                if AgentStepName.interview_coach.value in validated_live.blocked_sections
                else "completed"
            ),
            summary=(
                "Live interview content with invalid evidence was replaced with "
                "deterministic content."
                if AgentStepName.interview_coach.value in validated_live.blocked_sections
                else (
                    "Live AI prepared "
                    f"{len(sections.interview_coach.question_groups)} interview question groups."
                )
            ),
            duration_ms=sections.step_durations_ms.get(AgentStepName.interview_coach.value),
        ),
        _step_trace(
            name=AgentStepName.validation_gate,
            status=_validation_step_status(validation_status),
            summary=_validation_summary(validation_status, validation_warnings),
            started_at=validation_step_start,
        ),
        AgentStepTrace(
            name=AgentStepName.human_approval,
            status="completed",
            summary="The user approved the validated live draft before it replaced baseline text.",
            duration_ms=None,
        ),
    ]
    return AgentWorkflowResult(
        report=report,
        trace=AgentWorkflowTrace(
            mode=AgentWorkflowMode.langgraph,
            steps=traces,
            validation_warning_codes=[warning.code for warning in validation_warnings],
            validation_status=validation_status,
            duration_ms=_elapsed_ms(workflow_start) + (deterministic_result.trace.duration_ms or 0),
            provider=provider,
            model=model,
            token_usage=sections.token_usage,
            cost_estimate_usd=cost_estimate.amount_usd if cost_estimate else None,
            runtime_metadata=_runtime_metadata(
                settings=settings,
                status="completed",
                token_usage=sections.token_usage,
                cost_estimate=cost_estimate,
                blocked_live_sections=validated_live.blocked_sections,
            ),
        ),
    )


def with_langgraph_fallback_warning(
    deterministic_result: AgentWorkflowResult,
    exc: Exception,
    *,
    settings: Settings,
    live_duration_ms: int | None = None,
) -> AgentWorkflowResult:
    report = deterministic_result.report.model_copy(deep=True)
    warning = ValidationWarning(
        code="langgraph_unavailable",
        message=(
            "The LangGraph live-draft workflow was requested, but execution was unavailable; "
            f"returned deterministic fallback. Reason: {_public_error_summary(exc)}"
        ),
    )
    validation_warnings = _dedupe_warnings([*report.validation_warnings, warning])
    validation_status = _set_report_validation(report, validation_warnings)
    traces = [
        AgentStepTrace(
            name=AgentStepName.langgraph_runtime,
            status="failed",
            summary=(
                "LangGraph live drafting was unavailable; deterministic fallback returned. "
                f"Reason: {_public_error_summary(exc)}"
            ),
            duration_ms=live_duration_ms,
        ),
        *deterministic_result.trace.steps,
    ]
    return AgentWorkflowResult(
        report=report,
        trace=AgentWorkflowTrace(
            mode=AgentWorkflowMode.deterministic_fallback,
            steps=traces,
            validation_warning_codes=[warning.code for warning in validation_warnings],
            validation_status=validation_status,
            duration_ms=(deterministic_result.trace.duration_ms or 0) + (live_duration_ms or 0),
            provider=_runtime_provider(settings),
            model=_runtime_model(settings),
            token_usage=None,
            cost_estimate_usd=None,
            runtime_metadata=_runtime_metadata(
                settings=settings,
                status="failed",
                token_usage=None,
                fallback_reason=_public_error_summary(exc),
            ),
        ),
    )


def with_live_ai_limit_warning(
    deterministic_result: AgentWorkflowResult,
    *,
    settings: Settings,
) -> AgentWorkflowResult:
    """Return the completed deterministic report when live quota is unavailable."""

    report = deterministic_result.report.model_copy(deep=True)
    warning = ValidationWarning(
        code="live_ai_limit_reached",
        message=(
            "The deterministic report completed, but live drafting was skipped because the "
            "current plan's live AI limit was reached."
        ),
    )
    validation_warnings = _dedupe_warnings([*report.validation_warnings, warning])
    validation_status = _set_report_validation(report, validation_warnings)
    return AgentWorkflowResult(
        report=report,
        trace=AgentWorkflowTrace(
            mode=AgentWorkflowMode.deterministic_fallback,
            steps=[
                AgentStepTrace(
                    name=AgentStepName.langgraph_runtime,
                    status="degraded",
                    summary=(
                        "Live drafting was skipped because the live AI plan limit was reached; "
                        "the deterministic report completed successfully."
                    ),
                    duration_ms=0,
                ),
                *deterministic_result.trace.steps,
            ],
            validation_warning_codes=[warning.code for warning in validation_warnings],
            validation_status=validation_status,
            duration_ms=deterministic_result.trace.duration_ms,
            provider=_runtime_provider(settings),
            model=_runtime_model(settings),
            runtime_metadata=_runtime_metadata(
                settings=settings,
                status="skipped_limit",
                token_usage=None,
            ),
        ),
    )


def with_rejected_live_draft(
    deterministic_result: AgentWorkflowResult,
    *,
    settings: Settings,
    sections: LiveDraftSections,
    live_duration_ms: int,
) -> AgentWorkflowResult:
    """Retain the deterministic report while recording the explicit user decision."""

    provider = _runtime_provider(settings)
    model = _runtime_model(settings)
    cost_estimate = estimate_provider_cost(
        provider=provider,
        model=model,
        region=settings.vertex_region,
        token_usage=sections.token_usage,
    )
    return AgentWorkflowResult(
        report=deterministic_result.report.model_copy(deep=True),
        trace=AgentWorkflowTrace(
            mode=AgentWorkflowMode.deterministic_fallback,
            steps=[
                AgentStepTrace(
                    name=AgentStepName.langgraph_runtime,
                    status="completed",
                    summary="Generated and validated a live draft inside LangGraph.",
                    duration_ms=live_duration_ms,
                ),
                AgentStepTrace(
                    name=AgentStepName.human_approval,
                    status="degraded",
                    summary=(
                        "The user rejected the live draft; the deterministic report was retained."
                    ),
                    duration_ms=None,
                ),
                *deterministic_result.trace.steps,
            ],
            validation_warning_codes=deterministic_result.trace.validation_warning_codes,
            validation_status=deterministic_result.trace.validation_status,
            duration_ms=(deterministic_result.trace.duration_ms or 0) + live_duration_ms,
            provider=provider,
            model=model,
            token_usage=sections.token_usage,
            cost_estimate_usd=cost_estimate.amount_usd if cost_estimate else None,
            runtime_metadata=_runtime_metadata(
                settings=settings,
                status="rejected",
                token_usage=sections.token_usage,
                cost_estimate=cost_estimate,
            ),
        ),
    )


def _resume_match_agent(
    resume: ResumeProfile, job: JobProfile, match: MatchResult
) -> ResumeMatchAgentOutput:
    role = job.role_title or "this role"
    company = job.company or "the company"
    strongest_matches = [item.skill for item in match.matched_skills[:5]]
    missing = [item.skill for item in match.missing_skills if item.importance == "required"]
    weak = [item.skill for item in match.weak_skills[:5]]
    weak_areas = [*missing[:5], *weak]
    evidence_ids = _unique(
        evidence_id for item in match.matched_skills[:5] for evidence_id in item.resume_evidence_ids
    )

    if not _has_actionable_job_skills(job):
        summary = (
            f"ResumePilot cannot calculate a trustworthy fit for {role} at {company} yet. "
            "The job listing did not expose explicit required or preferred skills, so the "
            f"provisional score is capped at {match.score:.1f}/100 until the job evidence is "
            "clearer."
        )
    elif strongest_matches:
        summary = (
            f"The resume scores {match.score:.1f}/100 for {role} at {company}. "
            f"The strongest supported matches are {_human_list(strongest_matches)}."
        )
    else:
        summary = (
            f"The resume scores {match.score:.1f}/100 for {role} at {company}, but no "
            "resume evidence-backed skill matches were found."
        )
    if missing:
        summary += f" Required gaps to handle honestly: {_human_list(missing[:5])}."

    positioning = _positioning_statement(resume, match, strongest_matches, missing)
    return ResumeMatchAgentOutput(
        summary=summary,
        strongest_matches=strongest_matches,
        weak_areas=weak_areas,
        recommended_positioning=positioning,
        evidence_ids=evidence_ids,
        confidence=match.confidence,
    )


def _ats_optimizer_agent(
    base_report: ApplicationReport, match: MatchResult
) -> AtsOptimizerAgentOutput:
    section_recommendations = [
        "Keep supported keywords close to the project or experience evidence that proves them.",
        "Do not add missing skills to the resume unless the candidate can support them with facts.",
    ]
    if match.weak_skills:
        section_recommendations.append(
            "Move weak skills from a plain skills list into project bullets "
            "if the experience is true."
        )

    return AtsOptimizerAgentOutput(
        tailored_bullets=base_report.tailored_bullets,
        keyword_suggestions=base_report.ats_keywords,
        section_recommendations=section_recommendations,
    )


def _cover_letter_agent(
    resume: ResumeProfile, job: JobProfile, match: MatchResult
) -> CoverLetterAgentOutput:
    candidate_name = resume.candidate.name or "Candidate"
    role = job.role_title or "the role"
    company = job.company or "your team"
    matched_skills = [item.skill for item in match.matched_skills[:4]]
    evidence_ids = _unique(
        evidence_id for item in match.matched_skills[:4] for evidence_id in item.resume_evidence_ids
    )
    evidence_facts = _facts_for_ids(resume, evidence_ids[:2])

    skill_sentence = (
        f"My resume has direct evidence for {_human_list(matched_skills)}."
        if matched_skills
        else "My resume includes relevant project evidence that I would review against the role."
    )
    fact_sentence = (
        " ".join(_safe_fact_sentence(fact) for fact in evidence_facts)
        if evidence_facts
        else "I would use the attached job-fit report to position only validated experience."
    )
    confidence_note = _cover_letter_confidence_note(job, match)

    draft = (
        "Dear Hiring Team,\n\n"
        f"I am interested in {role} at {company}. {skill_sentence} {fact_sentence} "
        "I would keep the application focused on these supported strengths and avoid adding "
        "any missing tools or claims unless they are true and can be backed by evidence.\n\n"
        f"{confidence_note}\n\n"
        f"Sincerely,\n{candidate_name}"
    )
    return CoverLetterAgentOutput(
        draft=draft,
        confidence_note=confidence_note,
        evidence_ids=evidence_ids,
    )


def _interview_coach_agent(resume: ResumeProfile, match: MatchResult) -> InterviewCoachAgentOutput:
    matched_questions = [
        f"How have you used {item.skill} in the resume evidence for this role?"
        for item in match.matched_skills[:4]
    ] or ["Walk through the strongest technical evidence in your resume."]
    matched_evidence_ids = _unique(
        evidence_id for item in match.matched_skills[:4] for evidence_id in item.resume_evidence_ids
    )

    gap_questions = [
        f"The role asks for {item.skill}. What related experience do you have, "
        "and what would you learn first?"
        for item in match.missing_skills[:4]
    ] or ["Which part of this role would require the most preparation, and why?"]

    project_evidence_ids = [fact.id for fact in resume.projects[:2]]
    behavioral_evidence_ids = [
        fact.id for fact in [*resume.experience, *resume.projects] if fact.id
    ][:3]
    groups = [
        InterviewQuestionGroup(
            category="Technical",
            questions=matched_questions,
            suggested_answer_evidence_ids=matched_evidence_ids[:4],
        ),
        InterviewQuestionGroup(
            category="Project Deep Dive",
            questions=[
                "Pick one resume project and explain the architecture, trade-offs, "
                "and failure handling.",
                "What would you improve if you rebuilt that project today?",
            ],
            suggested_answer_evidence_ids=project_evidence_ids,
        ),
        InterviewQuestionGroup(
            category="Behavioral",
            questions=[
                "Tell me about a time you improved reliability, quality, or maintainability.",
                "How do you decide what to learn first when a role has a skill gap?",
            ],
            suggested_answer_evidence_ids=behavioral_evidence_ids,
        ),
        InterviewQuestionGroup(category="Gap-Focused", questions=gap_questions),
    ]
    return InterviewCoachAgentOutput(question_groups=groups)


def _build_executive_summary(fit: ResumeMatchAgentOutput) -> str:
    if fit.weak_areas:
        return (
            f"{fit.summary} Recommended positioning: {fit.recommended_positioning} "
            f"Weak areas to handle honestly: {_human_list(fit.weak_areas[:5])}."
        )
    return f"{fit.summary} Recommended positioning: {fit.recommended_positioning}"


def _positioning_statement(
    resume: ResumeProfile, match: MatchResult, matched_skills: list[str], missing: list[str]
) -> str:
    candidate = resume.candidate.name or "The candidate"
    if match.confidence == Confidence.low and not matched_skills and not match.missing_skills:
        return (
            f"{candidate} should review the job URL extraction before tailoring the resume; "
            "the current report is a requirements-quality warning, not a fit recommendation."
        )
    if match.score >= 75 and matched_skills:
        return (
            f"{candidate} should lead with evidence-backed strengths in "
            f"{_human_list(matched_skills[:3])}."
        )
    if match.score >= 50:
        return (
            f"{candidate} should position the resume around verified strengths and treat "
            f"{_human_list(missing[:3]) if missing else 'the remaining gaps'} as preparation items."
        )
    return (
        f"{candidate} should use this role as a gap-analysis target before heavily "
        "tailoring the resume."
    )


def _next_actions(
    base_report: ApplicationReport,
    fit: ResumeMatchAgentOutput,
    ats: AtsOptimizerAgentOutput,
) -> list[str]:
    actions = [*base_report.next_actions]
    if _has_warning(base_report.validation_warnings, "required_skills_unclear"):
        actions.insert(
            0,
            "Use a direct public job-detail URL with visible requirements, then rerun analysis "
            "before trusting the fit score.",
        )
    if fit.evidence_ids:
        actions.append(
            f"Review the main evidence IDs used for positioning: {', '.join(fit.evidence_ids[:5])}."
        )
    actions.extend(ats.section_recommendations)
    return _unique(actions)


def _cover_letter_confidence_note(job: JobProfile, match: MatchResult) -> str:
    if not job.required_skills and not job.preferred_skills:
        return (
            "Confidence note: job requirements were not extracted clearly, so do not use this "
            "draft until the job URL is reviewed and analysis is rerun."
        )
    if not job.company or not job.role_title:
        return (
            "Confidence note: company or role details were incomplete, so this draft avoids "
            "specific claims beyond validated resume evidence."
        )
    if match.score < 50:
        return "Confidence note: this is a low-fit draft; review gaps carefully before using it."
    return "Confidence note: this draft uses only validated resume evidence and supported matches."


def _facts_for_ids(resume: ResumeProfile, evidence_ids: list[str]) -> list[ResumeFact]:
    facts_by_id = {fact.id: fact for fact in resume.facts}
    return [facts_by_id[evidence_id] for evidence_id in evidence_ids if evidence_id in facts_by_id]


def validate_live_draft_sections(
    *,
    sections: LiveDraftSections,
    deterministic_report: ApplicationReport,
    resume: ResumeProfile,
    job: JobProfile,
) -> ValidatedLiveSections:
    warnings: list[ValidationWarning] = []
    blocked_sections: set[str] = set()

    executive_summary = _build_executive_summary(sections.resume_match)
    fit_warning = _live_text_block_warning(
        section=AgentStepName.resume_match,
        label="resume-match",
        text=executive_summary,
        evidence_ids=sections.resume_match.evidence_ids,
        resume=resume,
        job=job,
        require_evidence=True,
        validate_skills=True,
        expected_match_score=deterministic_report.match_score,
    )
    executive_summary = deterministic_report.executive_summary
    if fit_warning:
        warnings.append(fit_warning)
        blocked_sections.add(AgentStepName.resume_match.value)

    cover_letter = sections.cover_letter.draft
    cover_letter_evidence_ids = sections.cover_letter.evidence_ids
    cover_warning = _live_text_block_warning(
        section=AgentStepName.cover_letter,
        label="cover-letter",
        text=cover_letter,
        evidence_ids=cover_letter_evidence_ids,
        resume=resume,
        job=job,
        require_evidence=True,
        validate_skills=True,
        expected_match_score=None,
    )
    if cover_warning:
        warnings.append(cover_warning)
        blocked_sections.add(AgentStepName.cover_letter.value)
        cover_letter = deterministic_report.cover_letter
        cover_letter_evidence_ids = deterministic_report.cover_letter_evidence_ids

    interview_questions = sections.interview_coach.question_groups
    missing_interview_evidence = _missing_interview_evidence_ids(interview_questions, resume)
    if missing_interview_evidence:
        warnings.append(
            ValidationWarning(
                code="live_interview_coach_blocked",
                message=(
                    "Live interview content was replaced with deterministic content because "
                    "its evidence references were invalid."
                ),
                evidence_ids=missing_interview_evidence,
                severity=ValidationSeverity.block,
            )
        )
        blocked_sections.add(AgentStepName.interview_coach.value)
        interview_questions = deterministic_report.interview_questions

    return ValidatedLiveSections(
        executive_summary=executive_summary,
        cover_letter=cover_letter,
        cover_letter_evidence_ids=cover_letter_evidence_ids,
        interview_questions=interview_questions,
        warnings=warnings,
        blocked_sections=frozenset(blocked_sections),
    )


def _live_text_block_warning(
    *,
    section: AgentStepName,
    label: str,
    text: str,
    evidence_ids: list[str],
    resume: ResumeProfile,
    job: JobProfile,
    require_evidence: bool,
    validate_skills: bool,
    expected_match_score: float | None,
) -> ValidationWarning | None:
    facts_by_id = {fact.id: fact for fact in resume.facts}
    missing_evidence_ids = [
        evidence_id for evidence_id in evidence_ids if evidence_id not in facts_by_id
    ]
    evidence_text = " ".join(
        facts_by_id[evidence_id].text for evidence_id in evidence_ids if evidence_id in facts_by_id
    )
    reasons: set[str] = set()
    if missing_evidence_ids or (require_evidence and not evidence_ids):
        reasons.add("evidence references")

    unsupported_claims = find_unsupported_claims(
        text,
        evidence_text,
        allowed_organizations=(job.company,) if job.company else (),
    )
    reasons.update(finding.category.value for finding in unsupported_claims)

    if expected_match_score is not None and _contains_changed_match_score(
        text, expected_match_score
    ):
        reasons.add("match score")

    if validate_skills:
        evidence_skills = set(find_skills(evidence_text))
        if any(skill not in evidence_skills for skill in find_skills(text)):
            reasons.add("skills")

    if not reasons:
        return None
    reason_text = ", ".join(sorted(reasons))
    return ValidationWarning(
        code=f"live_{section.value}_blocked",
        message=(
            f"Live {label} text was replaced with deterministic content because it contained "
            f"unsupported {reason_text}."
        ),
        evidence_ids=list(dict.fromkeys([*evidence_ids, *missing_evidence_ids])),
        severity=ValidationSeverity.block,
    )


def _contains_changed_match_score(text: str, expected_score: float) -> bool:
    score_pattern = re.compile(
        r"\b(?:match|fit|score|scores|scored)\b[^\d]{0,16}"
        r"(?P<score>\d{1,3}(?:\.\d+)?)\s*(?:/\s*100|%)",
        re.IGNORECASE,
    )
    return any(
        abs(float(match.group("score")) - expected_score) > 0.05
        for match in score_pattern.finditer(text)
    )


def _missing_interview_evidence_ids(
    groups: list[InterviewQuestionGroup], resume: ResumeProfile
) -> list[str]:
    known_ids = {fact.id for fact in resume.facts}
    return list(
        dict.fromkeys(
            evidence_id
            for group in groups
            for evidence_id in group.suggested_answer_evidence_ids
            if evidence_id not in known_ids
        )
    )


def _safe_fact_sentence(fact: ResumeFact) -> str:
    return fact.text.rstrip(".") + "."


def _dedupe_warnings(warnings: list[ValidationWarning]) -> list[ValidationWarning]:
    seen: set[tuple[str, tuple[str, ...], str, ValidationSeverity]] = set()
    deduped: list[ValidationWarning] = []
    for warning in warnings:
        key = (warning.code, tuple(warning.evidence_ids), warning.message, warning.severity)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(warning)
    return deduped


def _set_report_validation(
    report: ApplicationReport,
    warnings: list[ValidationWarning],
) -> ValidationSeverity:
    validation_status = validation_status_from_warnings(warnings)
    report.validation_warnings = warnings
    report.validation_status = validation_status
    return validation_status


def _validation_step_status(validation_status: ValidationSeverity) -> str:
    return "completed" if validation_status == ValidationSeverity.pass_ else "degraded"


def _validation_summary(
    validation_status: ValidationSeverity,
    warnings: list[ValidationWarning],
) -> str:
    if validation_status == ValidationSeverity.pass_:
        return "Validation passed without warnings."
    if validation_status == ValidationSeverity.block:
        return (
            f"Validation blocked unsafe live content and used deterministic fallback; "
            f"recorded {len(warnings)} finding(s)."
        )
    return f"Validation returned {len(warnings)} warning(s)."


def _human_list(values: list[str]) -> str:
    clean_values = [value for value in values if value]
    if not clean_values:
        return "no strong evidence-backed matches"
    if len(clean_values) == 1:
        return clean_values[0]
    if len(clean_values) == 2:
        return f"{clean_values[0]} and {clean_values[1]}"
    return f"{', '.join(clean_values[:-1])}, and {clean_values[-1]}"


def _has_actionable_job_skills(job: JobProfile) -> bool:
    return bool(job.required_skills or job.preferred_skills)


def _has_warning(warnings: list[ValidationWarning], code: str) -> bool:
    return any(warning.code == code for warning in warnings)


def _unique(values) -> list:
    return list(dict.fromkeys(values))


def _step_trace(
    *,
    name: AgentStepName,
    status: str,
    summary: str,
    started_at: float,
) -> AgentStepTrace:
    return AgentStepTrace(
        name=name,
        status=status,
        summary=summary,
        duration_ms=_elapsed_ms(started_at),
    )


def _timed_call[OutputT](callback: Callable[[], OutputT]) -> tuple[OutputT, int]:
    started_at = perf_counter()
    result = callback()
    return result, _elapsed_ms(started_at)


def _elapsed_ms(started_at: float) -> int:
    return max(0, round((perf_counter() - started_at) * 1000))


def _step_duration(steps: list[AgentStepTrace], name: AgentStepName) -> int | None:
    for step in steps:
        if step.name == name:
            return step.duration_ms
    return None


def _runtime_provider(settings: Settings) -> str:
    provider = settings.llm_provider.strip().lower()
    return provider or "unknown"


def _runtime_model(settings: Settings) -> str:
    if _runtime_provider(settings) == "vertex":
        return f"google_genai/{settings.llm_model}"
    return settings.llm_model


def _runtime_metadata(
    *,
    settings: Settings,
    status: str,
    token_usage: AgentTokenUsage | None,
    cost_estimate: ProviderCostEstimate | None = None,
    fallback_reason: str | None = None,
    blocked_live_sections: frozenset[str] | None = None,
) -> dict[str, str | int | float | bool | None]:
    metadata: dict[str, str | int | float | bool | None] = {
        "workflow_runtime": "langgraph",
        "runtime_status": status,
        "provider": _runtime_provider(settings),
        "model": _runtime_model(settings),
        "token_usage_source": "langchain_message_usage" if token_usage else "unavailable",
        "cost_estimate_source": "unavailable",
    }
    if cost_estimate:
        metadata.update(cost_estimate.metadata)
        metadata["cost_estimate_usd"] = cost_estimate.amount_usd
    if fallback_reason:
        metadata["fallback_reason"] = fallback_reason
    if blocked_live_sections:
        metadata["blocked_live_sections"] = ",".join(sorted(blocked_live_sections))
    return metadata


def _public_error_summary(exc: Exception) -> str:
    del exc
    return "Live AI runtime failed or is unavailable."

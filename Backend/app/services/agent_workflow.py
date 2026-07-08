from app.schemas.agent import (
    AgentStepName,
    AgentStepTrace,
    AgentWorkflowMode,
    AgentWorkflowResult,
    AgentWorkflowTrace,
    AtsOptimizerAgentOutput,
    CoverLetterAgentOutput,
    InterviewCoachAgentOutput,
    ResumeMatchAgentOutput,
)
from app.schemas.common import ValidationWarning
from app.schemas.job import JobProfile
from app.schemas.match import MatchResult
from app.schemas.report import ApplicationReport, InterviewQuestionGroup
from app.schemas.resume import ResumeFact, ResumeProfile
from app.services.report_generator import generate_report
from app.services.validator import validate_report_against_resume


def run_application_agent_workflow(
    *,
    analysis_id: int,
    resume: ResumeProfile,
    job: JobProfile,
    match: MatchResult,
) -> AgentWorkflowResult:
    """Run the bounded application-writing workflow.

    This deterministic fallback mirrors the planned CrewAI agent sequence while keeping
    deterministic parsing, matching, and validation as the source of truth.
    """

    base_report = generate_report(analysis_id=analysis_id, resume=resume, job=job, match=match)
    traces = [
        AgentStepTrace(
            name=AgentStepName.jd_parser,
            status="completed",
            summary=(
                "Used structured JobProfile produced by deterministic job parsing; "
                "no hidden requirements inferred."
            ),
        )
    ]

    fit = _resume_match_agent(resume, job, match)
    traces.append(
        AgentStepTrace(
            name=AgentStepName.resume_match,
            status="completed",
            summary=f"Explained fit with {len(fit.evidence_ids)} resume evidence references.",
        )
    )

    ats = _ats_optimizer_agent(base_report, match)
    traces.append(
        AgentStepTrace(
            name=AgentStepName.ats_optimizer,
            status="completed",
            summary=(
                f"Prepared {len(ats.tailored_bullets)} bullet suggestions and "
                f"{len(ats.keyword_suggestions)} keyword suggestions."
            ),
        )
    )

    cover_letter = _cover_letter_agent(resume, job, match)
    traces.append(
        AgentStepTrace(
            name=AgentStepName.cover_letter,
            status="completed",
            summary=(
                "Drafted cover letter from matched resume evidence only; "
                f"{len(cover_letter.evidence_ids)} evidence references used."
            ),
        )
    )

    interview = _interview_coach_agent(resume, match)
    traces.append(
        AgentStepTrace(
            name=AgentStepName.interview_coach,
            status="completed",
            summary=f"Prepared {len(interview.question_groups)} interview question groups.",
        )
    )

    report = base_report.model_copy(
        update={
            "executive_summary": _build_executive_summary(fit),
            "tailored_bullets": ats.tailored_bullets,
            "ats_keywords": ats.keyword_suggestions,
            "cover_letter": cover_letter.draft,
            "interview_questions": interview.question_groups,
            "next_actions": _next_actions(base_report, fit, ats),
        }
    )

    validation_warnings = _dedupe_warnings(
        [*report.validation_warnings, *validate_report_against_resume(report, resume)]
    )
    report.validation_warnings = validation_warnings
    traces.append(
        AgentStepTrace(
            name=AgentStepName.validation_gate,
            status="completed" if not validation_warnings else "degraded",
            summary=(
                "Validation passed without warnings."
                if not validation_warnings
                else f"Validation returned {len(validation_warnings)} warning(s)."
            ),
        )
    )

    return AgentWorkflowResult(
        report=report,
        trace=AgentWorkflowTrace(
            mode=AgentWorkflowMode.deterministic_fallback,
            steps=traces,
            validation_warning_codes=[warning.code for warning in validation_warnings],
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

    summary = (
        f"The resume scores {match.score:.1f}/100 for {role} at {company}. "
        f"The strongest supported matches are {_human_list(strongest_matches)}."
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
    if fit.evidence_ids:
        actions.append(
            f"Review the main evidence IDs used for positioning: {', '.join(fit.evidence_ids[:5])}."
        )
    actions.extend(ats.section_recommendations)
    return _unique(actions)


def _cover_letter_confidence_note(job: JobProfile, match: MatchResult) -> str:
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


def _safe_fact_sentence(fact: ResumeFact) -> str:
    return fact.text.rstrip(".") + "."


def _dedupe_warnings(warnings: list[ValidationWarning]) -> list[ValidationWarning]:
    seen: set[tuple[str, tuple[str, ...], str]] = set()
    deduped: list[ValidationWarning] = []
    for warning in warnings:
        key = (warning.code, tuple(warning.evidence_ids), warning.message)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(warning)
    return deduped


def _human_list(values: list[str]) -> str:
    clean_values = [value for value in values if value]
    if not clean_values:
        return "no strong evidence-backed matches"
    if len(clean_values) == 1:
        return clean_values[0]
    if len(clean_values) == 2:
        return f"{clean_values[0]} and {clean_values[1]}"
    return f"{', '.join(clean_values[:-1])}, and {clean_values[-1]}"


def _unique(values) -> list:
    return list(dict.fromkeys(values))

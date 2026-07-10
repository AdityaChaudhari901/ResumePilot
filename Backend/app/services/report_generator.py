import re

from app.schemas.common import ValidationWarning
from app.schemas.job import JobProfile
from app.schemas.match import MatchResult
from app.schemas.report import (
    ApplicationReport,
    AtsKeywordSuggestion,
    InterviewQuestionGroup,
    TailoredBullet,
)
from app.schemas.resume import ResumeFact, ResumeProfile
from app.services.resume_evidence import has_dangling_fact_ending, starts_with_resume_action_verb

TAILORED_BULLET_LIMIT = 5
TAILORED_BULLET_SOURCE_SECTIONS = {"experience", "projects"}
MIN_TAILORED_FACT_WORDS = 5


def generate_report(
    *,
    analysis_id: int,
    resume: ResumeProfile,
    job: JobProfile,
    match: MatchResult,
    validation_warnings: list[ValidationWarning] | None = None,
) -> ApplicationReport:
    warnings = [*resume.warnings, *job.warnings, *(validation_warnings or [])]
    matched_names = [skill.skill for skill in match.matched_skills]
    missing_names = [skill.skill for skill in match.missing_skills]
    role = job.role_title or "this role"
    company = job.company or "the company"
    requirements_unclear = _has_warning(warnings, "required_skills_unclear")
    summary = _executive_summary(
        role,
        company,
        match.score,
        matched_names,
        missing_names,
        requirements_unclear=requirements_unclear,
    )

    return ApplicationReport(
        analysis_id=analysis_id,
        resume_id=resume.resume_id,
        job_id=job.job_id,
        executive_summary=summary,
        match_score=match.score,
        matched_skills=match.matched_skills,
        missing_skills=match.missing_skills,
        weak_skills=match.weak_skills,
        tailored_bullets=_tailored_bullets(resume, match),
        ats_keywords=_ats_keywords(match),
        cover_letter=_cover_letter(resume, job, match),
        interview_questions=_interview_questions(resume, job, match),
        validation_warnings=warnings,
        next_actions=_next_actions(match, warnings),
    )


def report_to_markdown(report: ApplicationReport) -> str:
    requirements_unclear = _has_warning(report.validation_warnings, "required_skills_unclear")
    lines = [
        "# Job Fit Report",
        "",
        "## 1. Executive Summary",
        report.executive_summary,
        "",
        "## 2. Match Score",
        f"{report.match_score:.1f}/100",
        "",
        "## 3. Matched Skills",
    ]
    lines.extend(
        f"- {item.skill} ({item.match_type}, evidence: {', '.join(item.resume_evidence_ids)})"
        for item in report.matched_skills
    )
    if not report.matched_skills:
        if requirements_unclear:
            lines.append(
                "- No matched skills available because explicit job requirements were not "
                "extracted from the listing."
            )
        else:
            lines.append("- No matched skills detected.")

    lines.extend(["", "## 4. Missing or Weak Skills"])
    lines.extend(
        f"- Missing {item.importance}: {item.skill}. {item.recommendation}"
        for item in report.missing_skills
    )
    lines.extend(f"- Weak: {item.skill}. {item.reason}" for item in report.weak_skills)
    if not report.missing_skills and not report.weak_skills:
        if requirements_unclear:
            lines.append(
                "- Missing skills cannot be determined until explicit job requirements are "
                "extracted."
            )
        else:
            lines.append("- No missing or weak skills detected.")

    lines.extend(["", "## 5. Tailored Resume Bullet Suggestions"])
    lines.extend(
        f"- {item.bullet} Evidence: {', '.join(item.evidence_ids)}"
        for item in report.tailored_bullets
    )
    if not report.tailored_bullets:
        lines.append("- No evidence-backed bullet suggestions available.")

    lines.extend(["", "## 6. ATS Keyword Suggestions"])
    lines.extend(f"- {item.keyword}: {item.note}" for item in report.ats_keywords)
    if not report.ats_keywords:
        lines.append("- No ATS keywords were extracted from this job listing.")

    lines.extend(["", "## 7. Cover Letter Draft", report.cover_letter])

    lines.extend(["", "## 8. Interview Preparation"])
    for group in report.interview_questions:
        lines.append(f"### {group.category}")
        lines.extend(f"- {question}" for question in group.questions)

    lines.extend(["", "## 9. Validation Warnings"])
    lines.extend(f"- {warning.code}: {warning.message}" for warning in report.validation_warnings)
    if not report.validation_warnings:
        lines.append("- No validation warnings.")

    lines.extend(["", "## 10. Next Actions"])
    lines.extend(f"- {action}" for action in report.next_actions)
    return "\n".join(lines).strip() + "\n"


def _executive_summary(
    role: str,
    company: str,
    score: float,
    matched_names: list[str],
    missing_names: list[str],
    *,
    requirements_unclear: bool,
) -> str:
    if requirements_unclear and not matched_names and not missing_names:
        return (
            f"For {role} at {company}, ResumePilot could not extract explicit job "
            f"requirements, so the provisional score is capped at {score:.1f}/100. "
            "Review the job URL extraction before tailoring the resume."
        )
    matched = ", ".join(matched_names[:5]) if matched_names else "no strong technical matches"
    missing = (
        ", ".join(missing_names[:5]) if missing_names else "no critical missing skills detected"
    )
    return (
        f"For {role} at {company}, the current resume scores {score:.1f}/100. "
        f"Strongest evidence-backed matches: {matched}. Main gaps: {missing}."
    )


def _tailored_bullets(resume: ResumeProfile, match: MatchResult) -> list[TailoredBullet]:
    facts_by_id = {fact.id: fact for fact in resume.facts}
    skills_by_fact_id: dict[str, list[str]] = {}
    fact_order: list[str] = []

    for matched_skill in match.matched_skills:
        evidence_id = _select_tailored_evidence_id(
            matched_skill.resume_evidence_ids,
            facts_by_id,
            selected_fact_ids=set(fact_order),
        )
        if not evidence_id:
            continue
        if evidence_id not in skills_by_fact_id:
            if len(fact_order) >= TAILORED_BULLET_LIMIT:
                continue
            skills_by_fact_id[evidence_id] = []
            fact_order.append(evidence_id)
        if matched_skill.skill not in skills_by_fact_id[evidence_id]:
            skills_by_fact_id[evidence_id].append(matched_skill.skill)

    bullets: list[TailoredBullet] = []
    for evidence_id in fact_order:
        fact = facts_by_id[evidence_id]
        jd_keywords = skills_by_fact_id[evidence_id][:4]
        bullets.append(
            TailoredBullet(
                bullet=_rewrite_fact_as_bullet(fact, jd_keywords),
                evidence_ids=[evidence_id],
                jd_keywords_used=jd_keywords,
                unsupported_claims=[],
            )
        )
    return bullets


def _select_tailored_evidence_id(
    evidence_ids: list[str],
    facts_by_id: dict[str, ResumeFact],
    *,
    selected_fact_ids: set[str],
) -> str | None:
    candidate_ids = [
        evidence_id
        for evidence_id in evidence_ids
        if _is_tailored_fact_candidate(facts_by_id.get(evidence_id))
    ]
    for evidence_id in candidate_ids:
        if evidence_id in selected_fact_ids:
            return evidence_id
    return candidate_ids[0] if candidate_ids else None


def _is_tailored_fact_candidate(fact: ResumeFact | None) -> bool:
    if not fact or fact.section not in TAILORED_BULLET_SOURCE_SECTIONS:
        return False
    text = _clean_fact_text(fact.text)
    if len(text.split()) < MIN_TAILORED_FACT_WORDS:
        return False
    if has_dangling_fact_ending(text):
        return False
    return starts_with_resume_action_verb(text)


def _rewrite_fact_as_bullet(fact: ResumeFact, skills: list[str]) -> str:
    text = _ensure_sentence(_clean_fact_text(fact.text))
    missing_keywords = [
        skill for skill in skills if skill and skill.casefold() not in text.casefold()
    ]
    if not missing_keywords:
        return text

    stem = text[:-1] if text.endswith(".") else text
    return f"{stem}, emphasizing {_human_list(missing_keywords[:3])} for the target role."


def _clean_fact_text(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    text = text.strip(" -*•\t")
    if text and text[0].islower():
        text = f"{text[0].upper()}{text[1:]}"
    return text


def _ensure_sentence(value: str) -> str:
    text = value.strip()
    if not text:
        return text
    if text.endswith((".", "!", "?")):
        return text
    return f"{text}."


def _ats_keywords(match: MatchResult) -> list[AtsKeywordSuggestion]:
    suggestions: list[AtsKeywordSuggestion] = []
    for item in match.matched_skills:
        suggestions.append(
            AtsKeywordSuggestion(
                keyword=item.skill,
                status="supported",
                evidence_ids=item.resume_evidence_ids,
                note="Supported by resume evidence and safe to emphasize.",
            )
        )
    for item in match.missing_skills:
        suggestions.append(
            AtsKeywordSuggestion(
                keyword=item.skill,
                status="add_only_if_true",
                note=(
                    "Missing from resume evidence. "
                    "Add only if the candidate truly has this experience."
                ),
            )
        )
    return suggestions[:12]


def _cover_letter(resume: ResumeProfile, job: JobProfile, match: MatchResult) -> str:
    candidate_name = resume.candidate.name or "Candidate"
    role = job.role_title or "the role"
    company = job.company or "your team"
    evidence_skills = (
        ", ".join(item.skill for item in match.matched_skills[:4]) or "relevant project experience"
    )
    opening = (
        f"I am interested in {role} at {company}. My resume includes "
        f"evidence-backed experience with {evidence_skills}, and I would "
        "position my application around those strengths while being clear "
        "about the gaps identified in the job-fit report."
    )
    return f"Dear Hiring Team,\n\n{opening}\n\nSincerely,\n{candidate_name}"


def _interview_questions(
    resume: ResumeProfile, job: JobProfile, match: MatchResult
) -> list[InterviewQuestionGroup]:
    evidence_ids = [
        item.resume_evidence_ids[0] for item in match.matched_skills if item.resume_evidence_ids
    ]
    technical = [
        f"How have you used {item.skill} in a project or work setting?"
        for item in match.matched_skills[:4]
    ] or ["Walk through the most technical project on your resume."]
    gaps = [
        f"The role asks for {item.skill}. How would you ramp up or demonstrate related experience?"
        for item in match.missing_skills[:4]
    ] or ["Which part of this role would require the most preparation?"]
    project = [
        "Pick one resume project and explain the architecture, trade-offs, and failure handling.",
        "What would you improve if you rebuilt that project today?",
    ]
    return [
        InterviewQuestionGroup(
            category="Technical",
            questions=technical,
            suggested_answer_evidence_ids=evidence_ids[:4],
        ),
        InterviewQuestionGroup(
            category="Project Deep Dive",
            questions=project,
            suggested_answer_evidence_ids=[fact.id for fact in resume.projects[:2]],
        ),
        InterviewQuestionGroup(category="Gap-Focused", questions=gaps),
    ]


def _next_actions(match: MatchResult, warnings: list[ValidationWarning]) -> list[str]:
    actions = ["Review extracted resume evidence and correct any low-confidence fields."]
    if _has_warning(warnings, "required_skills_unclear"):
        actions.insert(
            0,
            "Use a direct public job-detail URL with visible requirements, then rerun analysis "
            "before trusting the fit score.",
        )
    if match.missing_skills:
        actions.append(
            "Do not add missing skills unless true; use them as a learning checklist or add "
            "project/work evidence only when the experience is real."
        )
    if match.weak_skills:
        actions.append(
            "Strengthen weak skills by moving them from summary or skills lists into truthful "
            "project/work bullets with outcomes."
        )
    actions.append("Use tailored bullets as suggestions, then manually review before applying.")
    return actions


def _has_warning(warnings: list[ValidationWarning], code: str) -> bool:
    return any(warning.code == code for warning in warnings)


def _human_list(values: list[str]) -> str:
    clean_values = [value for value in values if value]
    if not clean_values:
        return ""
    if len(clean_values) == 1:
        return clean_values[0]
    if len(clean_values) == 2:
        return f"{clean_values[0]} and {clean_values[1]}"
    return f"{', '.join(clean_values[:-1])}, and {clean_values[-1]}"

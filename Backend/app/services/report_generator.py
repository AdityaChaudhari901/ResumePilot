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
    summary = _executive_summary(role, company, match.score, matched_names, missing_names)

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
        next_actions=_next_actions(match),
    )


def report_to_markdown(report: ApplicationReport) -> str:
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
        lines.append("- No matched skills detected.")

    lines.extend(["", "## 4. Missing or Weak Skills"])
    lines.extend(
        f"- Missing {item.importance}: {item.skill}. {item.recommendation}"
        for item in report.missing_skills
    )
    lines.extend(f"- Weak: {item.skill}. {item.reason}" for item in report.weak_skills)
    if not report.missing_skills and not report.weak_skills:
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
    role: str, company: str, score: float, matched_names: list[str], missing_names: list[str]
) -> str:
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
    bullets: list[TailoredBullet] = []
    used_facts: set[str] = set()
    for matched_skill in match.matched_skills[:5]:
        evidence_id = matched_skill.resume_evidence_ids[0]
        if evidence_id in used_facts:
            continue
        fact = facts_by_id.get(evidence_id)
        if not fact:
            continue
        bullets.append(
            TailoredBullet(
                bullet=_rewrite_fact_as_bullet(fact, matched_skill.skill),
                evidence_ids=[evidence_id],
                jd_keywords_used=[matched_skill.skill],
                unsupported_claims=[],
            )
        )
        used_facts.add(evidence_id)
    return bullets


def _rewrite_fact_as_bullet(fact: ResumeFact, skill: str) -> str:
    text = fact.text.rstrip(".")
    if skill.lower() not in text.lower():
        return f"{text}, aligning with {skill} requirements."
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


def _next_actions(match: MatchResult) -> list[str]:
    actions = ["Review extracted resume evidence and correct any low-confidence fields."]
    if match.missing_skills:
        actions.append(
            "Do not add missing skills unless true; use them as a learning or evidence checklist."
        )
    if match.weak_skills:
        actions.append("Strengthen weak skills with project/work evidence if accurate.")
    actions.append("Use tailored bullets as suggestions, then manually review before applying.")
    return actions

import re

from app.schemas.common import Confidence
from app.schemas.job import JobProfile, JobSkill
from app.schemas.match import MatchedSkill, MatchResult, MatchType, MissingSkill, WeakSkill
from app.schemas.resume import ResumeProfile, ResumeSkill
from app.services.skill_normalizer import is_inferred_match
from app.services.text import normalize_token

DOMAIN_KEYWORDS = {"fintech", "healthcare", "saas", "devops", "genai", "security", "analytics"}
ACTION_VERBS = {
    "built",
    "created",
    "designed",
    "implemented",
    "improved",
    "optimized",
    "launched",
    "developed",
}
NO_ACTIONABLE_SKILLS_SCORE_CAP = 25.0


def match_resume_to_job(resume: ResumeProfile, job: JobProfile) -> MatchResult:
    resume_skills = {skill.name: skill for skill in resume.skills}
    matched: list[MatchedSkill] = []
    weak: list[WeakSkill] = []
    missing: list[MissingSkill] = []

    required_values = _match_skill_group(
        job.required_skills, resume_skills, resume, matched, weak, missing
    )
    preferred_values = _match_skill_group(
        job.preferred_skills, resume_skills, resume, matched, weak, missing
    )

    required_score = _group_score(required_values)
    preferred_score = _group_score(preferred_values)
    responsibility_score = _responsibility_alignment(job, resume)
    experience_score = _experience_level_score(job)
    domain_score = _domain_keyword_score(job, resume)
    quality_score = _resume_quality_score(resume)

    total = (
        required_score * 0.40
        + responsibility_score * 0.20
        + preferred_score * 0.15
        + experience_score * 0.10
        + domain_score * 0.10
        + quality_score * 0.05
    )

    has_actionable_job_skills = bool(job.required_skills or job.preferred_skills)
    if not has_actionable_job_skills:
        total = min(total, NO_ACTIONABLE_SKILLS_SCORE_CAP)

    confidence = Confidence.high if job.required_skills and resume.skills else Confidence.medium
    if not has_actionable_job_skills or not job.required_skills or not resume.skills:
        confidence = Confidence.low

    return MatchResult(
        score=round(total, 2),
        required_skill_score=round(required_score, 2),
        preferred_skill_score=round(preferred_score, 2),
        responsibility_alignment_score=round(responsibility_score, 2),
        experience_level_score=round(experience_score, 2),
        domain_keyword_score=round(domain_score, 2),
        resume_quality_score=round(quality_score, 2),
        matched_skills=matched,
        missing_skills=missing,
        weak_skills=weak,
        confidence=confidence,
    )


def _match_skill_group(
    job_skills: list[JobSkill],
    resume_skills: dict[str, ResumeSkill],
    resume: ResumeProfile,
    matched: list[MatchedSkill],
    weak: list[WeakSkill],
    missing: list[MissingSkill],
) -> list[float]:
    values: list[float] = []
    all_resume_skill_names = set(resume_skills)
    for job_skill in job_skills:
        resume_skill = resume_skills.get(job_skill.name)
        if resume_skill:
            match_type = MatchType.exact
            match_value = 1.0
            confidence = Confidence.high
        elif is_inferred_match(job_skill.name, all_resume_skill_names):
            inferred_source = next(
                skill
                for skill in all_resume_skill_names
                if is_inferred_match(job_skill.name, {skill})
            )
            resume_skill = resume_skills[inferred_source]
            match_type = MatchType.inferred
            match_value = 0.5
            confidence = Confidence.medium
        else:
            values.append(0.5 if job_skill.importance == "preferred" else 0.0)
            missing.append(_missing_skill(job_skill))
            continue

        if not resume_skill.evidence_ids:
            values.append(0.5 if job_skill.importance == "preferred" else 0.0)
            missing.append(_missing_skill(job_skill))
            continue

        matched.append(
            MatchedSkill(
                skill=job_skill.name,
                match_type=match_type,
                resume_evidence_ids=resume_skill.evidence_ids,
                job_evidence_text=job_skill.evidence_text,
                confidence=confidence,
            )
        )
        if _is_weak_skill(resume_skill, resume):
            weak.append(
                WeakSkill(
                    skill=resume_skill.name,
                    resume_evidence_ids=resume_skill.evidence_ids,
                    reason=(
                        "Skill appears only in a skills/summary section "
                        "without project or experience evidence."
                    ),
                )
            )
            match_value = min(match_value, 0.5)
        values.append(match_value)
    return values


def _missing_skill(job_skill: JobSkill) -> MissingSkill:
    importance = "required" if job_skill.importance == "required" else "preferred"
    return MissingSkill(
        skill=job_skill.name,
        importance=importance,
        job_evidence_text=job_skill.evidence_text,
        why_it_matters=f"The job description explicitly lists {job_skill.name} as {importance}.",
        recommendation=(
            f"Do not add {job_skill.name} to the resume unless it is true; "
            "if you have real experience, add project or work evidence that names the tool, "
            "scope, and outcome. Otherwise use it as a preparation item."
        ),
    )


def _is_weak_skill(skill: ResumeSkill, resume: ResumeProfile) -> bool:
    fact_sections = {fact.id: fact.section for fact in resume.facts}
    sections = {fact_sections.get(evidence_id) for evidence_id in skill.evidence_ids}
    return not bool(sections & {"experience", "projects"})


def _group_score(values: list[float]) -> float:
    if not values:
        return 70.0
    return sum(values) / len(values) * 100


def _responsibility_alignment(job: JobProfile, resume: ResumeProfile) -> float:
    if not job.responsibilities:
        return 70.0
    resume_text = normalize_token(" ".join(fact.text for fact in resume.facts))
    if not resume_text:
        return 0.0
    scores: list[float] = []
    for responsibility in job.responsibilities:
        tokens = _meaningful_tokens(responsibility)
        if not tokens:
            continue
        matches = sum(1 for token in tokens if token in resume_text)
        scores.append(matches / len(tokens) * 100)
    return min(100.0, sum(scores) / len(scores)) if scores else 70.0


def _meaningful_tokens(text: str) -> set[str]:
    stop_words = {
        "the",
        "and",
        "for",
        "with",
        "you",
        "will",
        "our",
        "are",
        "that",
        "this",
        "from",
        "using",
    }
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", normalize_token(text))
        if token not in stop_words
    }


def _experience_level_score(job: JobProfile) -> float:
    level = (job.experience_level or "").lower()
    if not level:
        return 70.0
    if any(marker in level for marker in ("0-2", "0to2", "1-2", "junior", "entry")):
        return 100.0
    if any(marker in level for marker in ("3-5", "3to5", "4-6")):
        return 55.0
    if "5" in level or "senior" in level:
        return 35.0
    return 70.0


def _domain_keyword_score(job: JobProfile, resume: ResumeProfile) -> float:
    job_domains = DOMAIN_KEYWORDS & set(
        _meaningful_tokens(" ".join(job.keywords + job.responsibilities))
    )
    if not job_domains:
        return 70.0
    resume_tokens = _meaningful_tokens(" ".join(fact.text for fact in resume.facts))
    matched = job_domains & resume_tokens
    return len(matched) / len(job_domains) * 100


def _resume_quality_score(resume: ResumeProfile) -> float:
    if not resume.facts:
        return 0.0
    fact_text = " ".join(fact.text.lower() for fact in resume.facts)
    score = 30.0
    if any(verb in fact_text for verb in ACTION_VERBS):
        score += 25.0
    if re.search(r"\d+%|\b\d+x\b|\b\d+\+", fact_text):
        score += 20.0
    if any(skill.confidence == Confidence.high for skill in resume.skills):
        score += 15.0
    if resume.candidate.links:
        score += 10.0
    return min(score, 100.0)

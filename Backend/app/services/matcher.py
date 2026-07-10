import re
from collections.abc import Iterable

from app.schemas.common import Confidence
from app.schemas.job import JobProfile, JobSkill
from app.schemas.match import (
    EVIDENCE_V2_COMPONENT_WEIGHTS,
    MatchedSkill,
    MatchResult,
    MatchScoreBreakdown,
    MatchScoreComponent,
    MatchScoreComponentKey,
    MatchScoreComponentStatus,
    MatchScoreStatus,
    MatchType,
    MissingSkill,
    ScoringVersion,
    WeakSkill,
    evidence_v2_effective_weights,
)
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
UNCLEAR_REQUIRED_SKILLS_SCORE_CAP = 60.0
DETERMINISTIC_V1_SCORING_VERSION = ScoringVersion.deterministic_v1
CURRENT_SCORING_VERSION = ScoringVersion.evidence_v2
RESPONSIBILITY_TOKEN_ALIASES = {
    "apis": "api",
    "applications": "application",
    "built": "build",
    "building": "build",
    "created": "create",
    "creating": "create",
    "deployed": "deploy",
    "deployment": "deploy",
    "deployments": "deploy",
    "developed": "develop",
    "developing": "develop",
    "implemented": "implement",
    "implementing": "implement",
    "improved": "improve",
    "improving": "improve",
    "led": "lead",
    "leading": "lead",
    "maintained": "maintain",
    "maintaining": "maintain",
    "optimized": "optimize",
    "optimizing": "optimize",
    "owned": "own",
    "owning": "own",
    "reliability": "reliable",
    "services": "service",
    "systems": "system",
    "tested": "test",
    "testing": "test",
    "tests": "test",
    "workflows": "workflow",
}
CANDIDATE_EXPERIENCE_PREFIX_PATTERN = (
    r"(?P<candidate_prefix>"
    r"i\s+(?:have|bring|offer|possess)\s+|"
    r"(?:[a-z][a-z0-9+&./-]*\s+){0,6}"
    r"(?:engineer|developer|architect|analyst|scientist|professional|manager|specialist|"
    r"consultant|designer|leader|executive|administrator|coordinator|owner|director)"
    r"\s+with\s+"
    r")?"
)
CANDIDATE_EXPERIENCE_CLAIM_PATTERN = re.compile(
    r"^\s*"
    + CANDIDATE_EXPERIENCE_PREFIX_PATTERN
    + r"(?:over|more\s+than|about|approximately)?\s*"
    + r"(?P<years>\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)"
    r"(?:\s+of\s+|\s+|\s*[’']\s*)"
    r"(?:[a-z][a-z0-9+&./-]*\s+){0,5}experience\b",
    re.IGNORECASE,
)
CANDIDATE_TOTAL_EXPERIENCE_PATTERN = re.compile(
    r"^\s*(?:(?:total|overall)\s+)?(?:professional\s+)?experience\s*:\s*"
    r"(?P<years>\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b",
    re.IGNORECASE,
)
EXPERIENCE_NUMBER_WORDS = {
    "zero": 0.0,
    "one": 1.0,
    "two": 2.0,
    "three": 3.0,
    "four": 4.0,
    "five": 5.0,
    "six": 6.0,
    "seven": 7.0,
    "eight": 8.0,
    "nine": 9.0,
    "ten": 10.0,
    "eleven": 11.0,
    "twelve": 12.0,
    "thirteen": 13.0,
    "fourteen": 14.0,
    "fifteen": 15.0,
    "sixteen": 16.0,
    "seventeen": 17.0,
    "eighteen": 18.0,
    "nineteen": 19.0,
    "twenty": 20.0,
}
CANDIDATE_WORD_EXPERIENCE_PATTERN = re.compile(
    r"^\s*"
    + CANDIDATE_EXPERIENCE_PREFIX_PATTERN
    + r"(?:over|more\s+than|about|approximately)?\s*"
    + r"(?P<years>"
    + "|".join(EXPERIENCE_NUMBER_WORDS)
    + r")\s+(?:years?|yrs?)"
    r"(?:\s+of\s+|\s+|\s*[’']\s*)"
    r"(?:[a-z][a-z0-9+&./-]*\s+){0,5}experience\b",
    re.IGNORECASE,
)
COLLECTIVE_CANDIDATE_EXPERIENCE_PATTERN = re.compile(
    r"\b(?:combined|collective|collectively)\b|"
    r"\b(?:among|across)\s+(?:(?:our|the)\s+)?(?:engineering\s+)?"
    r"(?:teams?|company|organization|consultants?|engineers?|project\s+contributors?)\b|"
    r"\brepresented\s+among\s+(?:project\s+)?contributors?\b",
    re.IGNORECASE,
)


def match_resume_to_job(
    resume: ResumeProfile,
    job: JobProfile,
    *,
    scoring_version: ScoringVersion = CURRENT_SCORING_VERSION,
) -> MatchResult:
    if scoring_version == CURRENT_SCORING_VERSION:
        return _match_resume_to_job_v2(resume, job)
    if scoring_version == DETERMINISTIC_V1_SCORING_VERSION:
        return _match_resume_to_job_v1(resume, job)
    raise ValueError(f"Unsupported executable scoring version: {scoring_version}")


def _match_resume_to_job_v1(resume: ResumeProfile, job: JobProfile) -> MatchResult:
    resume_skills = {skill.name: skill for skill in resume.skills}
    matched: list[MatchedSkill] = []
    weak: list[WeakSkill] = []
    missing: list[MissingSkill] = []

    required_values = _match_skill_group(
        job.required_skills,
        resume_skills,
        resume,
        matched,
        weak,
        missing,
        missing_preferred_credit=0.5,
        weak_inferred_credit=0.5,
        align_confidence_with_evidence=False,
    )
    preferred_values = _match_skill_group(
        job.preferred_skills,
        resume_skills,
        resume,
        matched,
        weak,
        missing,
        missing_preferred_credit=0.5,
        weak_inferred_credit=0.5,
        align_confidence_with_evidence=False,
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
        scoring_version=DETERMINISTIC_V1_SCORING_VERSION,
        score_status=(
            MatchScoreStatus.provisional
            if not has_actionable_job_skills or not job.required_skills
            else MatchScoreStatus.scored
        ),
    )


def _match_resume_to_job_v2(resume: ResumeProfile, job: JobProfile) -> MatchResult:
    resume_skills = {skill.name: skill for skill in resume.skills}
    matched: list[MatchedSkill] = []
    weak: list[WeakSkill] = []
    missing: list[MissingSkill] = []

    required_start = len(matched)
    required_values = _match_skill_group(
        job.required_skills,
        resume_skills,
        resume,
        matched,
        weak,
        missing,
        missing_preferred_credit=0.0,
        weak_inferred_credit=0.25,
        align_confidence_with_evidence=True,
    )
    required_matches = matched[required_start:]
    preferred_start = len(matched)
    preferred_values = _match_skill_group(
        job.preferred_skills,
        resume_skills,
        resume,
        matched,
        weak,
        missing,
        missing_preferred_credit=0.0,
        weak_inferred_credit=0.25,
        align_confidence_with_evidence=True,
    )
    preferred_matches = matched[preferred_start:]

    required_component = _skill_component(
        MatchScoreComponentKey.required_skills,
        job.required_skills,
        required_values,
        required_matches,
        unknown_when_empty=True,
    )
    preferred_component = _skill_component(
        MatchScoreComponentKey.preferred_skills,
        job.preferred_skills,
        preferred_values,
        preferred_matches,
        unknown_when_empty=False,
    )
    responsibility_component = _responsibility_component_v2(job, resume)
    experience_component = _experience_component_v2(job, resume)
    domain_component = _domain_component_v2(job, resume)
    evidence_component = _evidence_strength_component(matched, resume)

    has_actionable_job_skills = bool(job.required_skills or job.preferred_skills)
    score_caps: list[float] = []
    if not has_actionable_job_skills:
        score_caps.append(NO_ACTIONABLE_SKILLS_SCORE_CAP)
    elif not job.required_skills:
        score_caps.append(UNCLEAR_REQUIRED_SKILLS_SCORE_CAP)
    score_cap = min(score_caps, default=None)
    score_status = (
        MatchScoreStatus.provisional
        if score_cap is not None or experience_component.status == MatchScoreComponentStatus.unknown
        else MatchScoreStatus.scored
    )
    breakdown = _build_score_breakdown(
        [
            required_component,
            responsibility_component,
            preferred_component,
            experience_component,
            domain_component,
            evidence_component,
        ],
        score_status=score_status,
        score_cap=score_cap,
    )
    evidence_score = evidence_component.score or 0.0
    confidence = _match_confidence_v2(
        job=job,
        resume=resume,
        required_score=required_component.score,
        evidence_score=evidence_score,
        matched_count=len(matched),
    )

    return MatchResult(
        score=breakdown.total_score,
        required_skill_score=round(required_component.score or 0.0, 2),
        preferred_skill_score=round(preferred_component.score or 0.0, 2),
        responsibility_alignment_score=round(responsibility_component.score or 0.0, 2),
        experience_level_score=round(experience_component.score or 0.0, 2),
        domain_keyword_score=round(domain_component.score or 0.0, 2),
        resume_quality_score=round(_resume_quality_score(resume), 2),
        matched_skills=matched,
        missing_skills=missing,
        weak_skills=weak,
        confidence=confidence,
        scoring_version=CURRENT_SCORING_VERSION,
        score_status=score_status,
        score_breakdown=breakdown,
    )


def _match_skill_group(
    job_skills: list[JobSkill],
    resume_skills: dict[str, ResumeSkill],
    resume: ResumeProfile,
    matched: list[MatchedSkill],
    weak: list[WeakSkill],
    missing: list[MissingSkill],
    *,
    missing_preferred_credit: float,
    weak_inferred_credit: float,
    align_confidence_with_evidence: bool,
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
            values.append(missing_preferred_credit if job_skill.importance == "preferred" else 0.0)
            missing.append(_missing_skill(job_skill))
            continue

        if not resume_skill.evidence_ids:
            values.append(missing_preferred_credit if job_skill.importance == "preferred" else 0.0)
            missing.append(_missing_skill(job_skill))
            continue

        is_weak = _is_weak_skill(resume_skill, resume)
        if is_weak and align_confidence_with_evidence:
            confidence = Confidence.low if match_type == MatchType.inferred else Confidence.medium
        matched.append(
            MatchedSkill(
                skill=job_skill.name,
                match_type=match_type,
                resume_evidence_ids=resume_skill.evidence_ids,
                job_evidence_text=job_skill.evidence_text,
                confidence=confidence,
            )
        )
        if is_weak:
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
            match_value = min(
                match_value,
                weak_inferred_credit if match_type == MatchType.inferred else 0.5,
            )
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


def _skill_component(
    key: MatchScoreComponentKey,
    job_skills: list[JobSkill],
    values: list[float],
    matched: list[MatchedSkill],
    *,
    unknown_when_empty: bool,
) -> MatchScoreComponent:
    if not job_skills:
        status = (
            MatchScoreComponentStatus.unknown
            if unknown_when_empty
            else MatchScoreComponentStatus.not_applicable
        )
        explanation = (
            "No explicit required skills were extracted from the reviewed job description."
            if unknown_when_empty
            else "The reviewed job description does not list preferred skills."
        )
        return _unscored_component(key, status=status, explanation=explanation)

    score = round(sum(values) / len(values) * 100, 2)
    evidence_ids = _unique_values(
        evidence_id for item in matched for evidence_id in item.resume_evidence_ids
    )
    label = "required" if key == MatchScoreComponentKey.required_skills else "preferred"
    return MatchScoreComponent(
        key=key,
        status=MatchScoreComponentStatus.scored,
        score=score,
        base_weight=EVIDENCE_V2_COMPONENT_WEIGHTS[key],
        effective_weight=0,
        contribution=0,
        matched_count=len(matched),
        total_count=len(job_skills),
        evidence_ids=evidence_ids,
        explanation=(
            f"{len(matched)} of {len(job_skills)} {label} skills have resume evidence; "
            "inferred and section-only evidence receives partial credit."
        ),
    )


def _responsibility_component_v2(
    job: JobProfile,
    resume: ResumeProfile,
) -> MatchScoreComponent:
    responsibility_tokens = [
        tokens for item in job.responsibilities if (tokens := _canonical_meaningful_tokens(item))
    ]
    if not responsibility_tokens:
        return _unscored_component(
            MatchScoreComponentKey.responsibilities,
            status=MatchScoreComponentStatus.not_applicable,
            explanation=(
                "No scorable responsibilities were extracted from the reviewed job description."
            ),
        )

    evidence_facts = [fact for fact in resume.facts if fact.section in {"experience", "projects"}]
    if not evidence_facts:
        return _scored_component(
            MatchScoreComponentKey.responsibilities,
            score=0,
            matched_count=0,
            total_count=len(responsibility_tokens),
            evidence_ids=[],
            explanation=(
                "The resume has no project or work facts that can support the listed "
                "responsibilities."
            ),
        )

    facts_with_tokens = [
        (fact.id, _canonical_meaningful_tokens(fact.text)) for fact in evidence_facts
    ]
    resume_tokens = set().union(*(fact_tokens for _, fact_tokens in facts_with_tokens))
    scores: list[float] = []
    matched_responsibilities = 0
    supporting_ids: list[str] = []
    for tokens in responsibility_tokens:
        overlap = tokens & resume_tokens
        score = len(overlap) / len(tokens) * 100
        scores.append(score)
        if overlap:
            matched_responsibilities += 1
            supporting_ids.extend(
                fact_id for fact_id, fact_tokens in facts_with_tokens if overlap & fact_tokens
            )

    score = round(sum(scores) / len(scores), 2)
    return _scored_component(
        MatchScoreComponentKey.responsibilities,
        score=score,
        matched_count=matched_responsibilities,
        total_count=len(responsibility_tokens),
        evidence_ids=_unique_values(supporting_ids),
        explanation=(
            f"{matched_responsibilities} of {len(responsibility_tokens)} responsibilities have "
            "exact-token support in project or work evidence."
        ),
    )


def _experience_component_v2(
    job: JobProfile,
    resume: ResumeProfile,
) -> MatchScoreComponent:
    required_years = _minimum_job_experience_years(job.experience_level)
    if required_years is None:
        status = (
            MatchScoreComponentStatus.unknown
            if job.experience_level
            else MatchScoreComponentStatus.not_applicable
        )
        explanation = (
            "The job experience requirement could not be normalized safely."
            if job.experience_level
            else "The reviewed job description does not state an experience requirement."
        )
        return _unscored_component(
            MatchScoreComponentKey.experience,
            status=status,
            explanation=explanation,
        )
    if required_years == 0:
        return _scored_component(
            MatchScoreComponentKey.experience,
            score=100,
            matched_count=None,
            total_count=None,
            evidence_ids=[],
            explanation=(
                "The role states an entry-level or zero-year minimum experience requirement."
            ),
        )

    candidate_years, evidence_ids = _candidate_experience_years(resume)
    if candidate_years is None:
        return _unscored_component(
            MatchScoreComponentKey.experience,
            status=MatchScoreComponentStatus.unknown,
            explanation=(
                f"The job requires at least {required_years:g} years, but the resume has no "
                "explicit structured tenure claim."
            ),
        )

    score = round(max(0.0, min(100.0, candidate_years / required_years * 100)), 2)
    return _scored_component(
        MatchScoreComponentKey.experience,
        score=score,
        matched_count=None,
        total_count=None,
        evidence_ids=evidence_ids,
        explanation=(
            f"The resume explicitly states {candidate_years:g} years against a "
            f"{required_years:g}-year minimum."
        ),
    )


def _domain_component_v2(job: JobProfile, resume: ResumeProfile) -> MatchScoreComponent:
    job_domains = DOMAIN_KEYWORDS & set(
        _canonical_meaningful_tokens(" ".join(job.keywords + job.responsibilities))
    )
    if not job_domains:
        return _unscored_component(
            MatchScoreComponentKey.domain,
            status=MatchScoreComponentStatus.not_applicable,
            explanation=(
                "No supported domain keyword was extracted from the reviewed job description."
            ),
        )

    evidence: list[str] = []
    matched_domains: set[str] = set()
    for fact in resume.facts:
        fact_domains = job_domains & _canonical_meaningful_tokens(fact.text)
        if fact_domains:
            matched_domains.update(fact_domains)
            evidence.append(fact.id)
    score = round(len(matched_domains) / len(job_domains) * 100, 2)
    return _scored_component(
        MatchScoreComponentKey.domain,
        score=score,
        matched_count=len(matched_domains),
        total_count=len(job_domains),
        evidence_ids=_unique_values(evidence),
        explanation=(
            f"{len(matched_domains)} of {len(job_domains)} extracted domain keywords have "
            "exact-token resume evidence."
        ),
    )


def _evidence_strength_component(
    matched: list[MatchedSkill],
    resume: ResumeProfile,
) -> MatchScoreComponent:
    if not matched:
        return _unscored_component(
            MatchScoreComponentKey.evidence_strength,
            status=MatchScoreComponentStatus.not_applicable,
            explanation="No matched skills are available for evidence-strength review.",
        )

    fact_sections = {fact.id: fact.section for fact in resume.facts}
    strong_count = 0
    evidence_ids: list[str] = []
    for item in matched:
        evidence_ids.extend(item.resume_evidence_ids)
        if any(
            fact_sections.get(evidence_id) in {"experience", "projects"}
            for evidence_id in item.resume_evidence_ids
        ):
            strong_count += 1
    weak_count = len(matched) - strong_count
    score = round((strong_count + weak_count * 0.5) / len(matched) * 100, 2)
    return MatchScoreComponent(
        key=MatchScoreComponentKey.evidence_strength,
        status=MatchScoreComponentStatus.scored,
        score=score,
        base_weight=EVIDENCE_V2_COMPONENT_WEIGHTS[MatchScoreComponentKey.evidence_strength],
        effective_weight=0,
        contribution=0,
        matched_count=strong_count,
        total_count=len(matched),
        evidence_ids=_unique_values(evidence_ids),
        explanation=(
            f"{strong_count} of {len(matched)} matched skills are supported by project or work "
            "facts; section-only matches are labeled as weaker evidence."
        ),
    )


def _build_score_breakdown(
    components: list[MatchScoreComponent],
    *,
    score_status: MatchScoreStatus,
    score_cap: float | None,
) -> MatchScoreBreakdown:
    effective_weights = evidence_v2_effective_weights(components)

    weighted_components: list[MatchScoreComponent] = []
    for component in components:
        effective_weight = effective_weights.get(component.key, 0.0)
        contribution = (
            round((component.score or 0.0) * effective_weight / 100, 2)
            if component.status == MatchScoreComponentStatus.scored
            else 0.0
        )
        weighted_components.append(
            MatchScoreComponent.model_validate(
                {
                    **component.model_dump(mode="json"),
                    "effective_weight": effective_weight,
                    "contribution": contribution,
                }
            )
        )
    uncapped_score = round(sum(component.contribution for component in weighted_components), 2)
    score_ceiling = score_cap if score_cap is not None else 100.0
    total_score = round(min(uncapped_score, score_ceiling), 2)
    return MatchScoreBreakdown(
        scoring_version=CURRENT_SCORING_VERSION,
        score_status=score_status,
        uncapped_score=uncapped_score,
        score_cap=score_cap,
        total_score=total_score,
        components=weighted_components,
    )


def _scored_component(
    key: MatchScoreComponentKey,
    *,
    score: float,
    matched_count: int | None,
    total_count: int | None,
    evidence_ids: list[str],
    explanation: str,
) -> MatchScoreComponent:
    return MatchScoreComponent(
        key=key,
        status=MatchScoreComponentStatus.scored,
        score=round(score, 2),
        base_weight=EVIDENCE_V2_COMPONENT_WEIGHTS[key],
        effective_weight=0,
        contribution=0,
        matched_count=matched_count,
        total_count=total_count,
        evidence_ids=evidence_ids,
        explanation=explanation,
    )


def _unscored_component(
    key: MatchScoreComponentKey,
    *,
    status: MatchScoreComponentStatus,
    explanation: str,
) -> MatchScoreComponent:
    return MatchScoreComponent(
        key=key,
        status=status,
        score=None,
        base_weight=EVIDENCE_V2_COMPONENT_WEIGHTS[key],
        effective_weight=0,
        contribution=0,
        explanation=explanation,
    )


def _minimum_job_experience_years(experience_level: str | None) -> float | None:
    if not experience_level:
        return None
    normalized = normalize_token(experience_level).replace("to", "-")
    range_match = re.search(r"\b(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\b", normalized)
    if range_match:
        return float(range_match.group(1))
    minimum_match = re.search(r"\b(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)?\b", normalized)
    if minimum_match:
        return float(minimum_match.group(1))
    stated_years_match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b", normalized)
    if stated_years_match:
        return float(stated_years_match.group(1))
    if any(marker in normalized for marker in ("entry", "junior", "fresher")):
        return 0.0
    if "senior" in normalized:
        return 5.0
    return None


def _candidate_experience_years(resume: ResumeProfile) -> tuple[float | None, list[str]]:
    claims: list[tuple[float, str]] = []
    for fact in resume.facts:
        if fact.section not in {"summary", "experience"}:
            continue
        match = CANDIDATE_EXPERIENCE_CLAIM_PATTERN.match(fact.text)
        if match is None:
            match = CANDIDATE_TOTAL_EXPERIENCE_PATTERN.match(fact.text)
        word_match = CANDIDATE_WORD_EXPERIENCE_PATTERN.match(fact.text)
        if (match is None and word_match is None) or COLLECTIVE_CANDIDATE_EXPERIENCE_PATTERN.search(
            fact.text
        ):
            continue
        years = (
            float(match.group("years"))
            if match is not None
            else EXPERIENCE_NUMBER_WORDS[word_match.group("years").casefold()]
        )
        claims.append((years, fact.id))
    if not claims:
        return None, []
    maximum = max(years for years, _ in claims)
    evidence_ids = _unique_values(fact_id for years, fact_id in claims if years == maximum)
    return maximum, evidence_ids


def _canonical_meaningful_tokens(text: str) -> set[str]:
    return {RESPONSIBILITY_TOKEN_ALIASES.get(token, token) for token in _meaningful_tokens(text)}


def _unique_values(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def _match_confidence_v2(
    *,
    job: JobProfile,
    resume: ResumeProfile,
    required_score: float | None,
    evidence_score: float,
    matched_count: int,
) -> Confidence:
    if not job.required_skills or not resume.skills or matched_count == 0:
        return Confidence.low
    if (required_score or 0) >= 75 and evidence_score >= 75:
        return Confidence.high
    return Confidence.medium


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

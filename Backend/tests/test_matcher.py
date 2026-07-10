import pytest

from app.schemas.match import MatchScoreBreakdown
from app.services.job_parser import parse_job_profile
from app.services.matcher import (
    CURRENT_SCORING_VERSION,
    DETERMINISTIC_V1_SCORING_VERSION,
    match_resume_to_job,
)
from app.services.resume_parser import parse_resume_profile


def test_matcher_scores_required_and_missing_skills(sample_resume_text, sample_job_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)

    result = match_resume_to_job(resume, job)

    matched = {skill.skill for skill in result.matched_skills}
    missing = {skill.skill for skill in result.missing_skills}
    assert {"Python", "FastAPI", "REST API"} <= matched
    assert "Docker" in missing
    assert 60 <= result.score < 75
    assert all(skill.resume_evidence_ids for skill in result.matched_skills)
    assert result.scoring_version == CURRENT_SCORING_VERSION
    assert result.score_breakdown is not None
    assert result.score_breakdown.total_score == result.score
    assert (
        round(
            sum(component.contribution for component in result.score_breakdown.components),
            2,
        )
        == result.score_breakdown.uncapped_score
    )


def test_matcher_caps_score_when_job_skills_are_unclear(sample_resume_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(
        """Persistent careers

        Join our engineering team and collaborate with product teams on customer-facing
        software. You will improve internal workflows, contribute to platform quality,
        and communicate with stakeholders across delivery teams.
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)

    assert "required_skills_unclear" in {warning.code for warning in job.warnings}
    assert result.score <= 25
    assert result.confidence == "low"
    assert result.matched_skills == []
    assert result.missing_skills == []
    assert result.score_status == "provisional"


def test_evidence_v2_does_not_credit_missing_preferred_or_absent_dimensions():
    resume = parse_resume_profile(
        """Candidate

        Skills
        Python

        Projects
        Built a Python service.
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Platform Engineer

        Preferred qualifications:
        - Preferred Docker experience.
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)
    preferred = _component(result, "preferred_skills")
    required = _component(result, "required_skills")
    experience = _component(result, "experience")

    assert result.preferred_skill_score == 0
    assert preferred.score == 0
    assert preferred.matched_count == 0
    assert preferred.total_count == 1
    assert required.status == "unknown"
    assert required.score is None
    assert experience.status == "not_applicable"
    assert experience.score is None
    assert result.score_status == "provisional"
    assert result.score <= 60


def test_evidence_v2_uses_token_boundaries_for_responsibilities():
    resume = parse_resume_profile(
        """Candidate

        Skills
        Python

        Projects
        Maintained an ongoing Python project.
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Go Engineer

        Responsibilities:
        - Go ownership delivery excellence.

        Requirements:
        - Required Python experience.
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)
    responsibility = _component(result, "responsibilities")

    assert responsibility.status == "scored"
    assert responsibility.score == 0
    assert result.responsibility_alignment_score == 0


def test_evidence_v2_ranks_explicit_senior_experience_above_junior_experience():
    job_text = """Role: Senior Backend Engineer

    Responsibilities:
    - Build Python services and lead platform reliability.

    Requirements:
    - Required Python experience.

    Experience: 5+ years.
    """
    junior = parse_resume_profile(
        """Junior Candidate

        Summary
        1 year of professional experience.

        Skills
        Python

        Projects
        Built Python services for a student project.
        """,
        resume_id=1,
    )
    senior = parse_resume_profile(
        """Senior Candidate

        Summary
        10 years of professional experience.

        Skills
        Python

        Experience
        Built Python services and led platform reliability.
        """,
        resume_id=2,
    )
    job = parse_job_profile(job_text, job_id=1)

    junior_match = match_resume_to_job(junior, job)
    senior_match = match_resume_to_job(senior, job)

    assert _component(junior_match, "experience").score == 20
    assert _component(senior_match, "experience").score == 100
    assert senior_match.score >= junior_match.score + 5


@pytest.mark.parametrize(
    "tenure_claim",
    [
        "10 years’ professional experience.",
        "10 years' professional experience.",
        "Total experience: 10 years.",
        "Experience: 10 years.",
        "10 years of relevant experience.",
        "10 years of backend engineering experience.",
        "10 years of data science experience.",
        "10 years of cloud platform engineering experience.",
        "Ten years of professional experience.",
        "I have ten years of professional experience.",
        "Senior Engineer with ten years of professional experience.",
        "Senior Product Manager with 10 years of professional experience.",
        "Machine Learning Engineer with 10 years of professional experience.",
    ],
)
def test_evidence_v2_recognizes_candidate_centric_tenure_variants(tenure_claim):
    resume = parse_resume_profile(
        f"""Senior Candidate

        Summary
        {tenure_claim}

        Skills
        Python

        Experience
        Built Python services and led platform reliability.
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Senior Backend Engineer

        Responsibilities
        - Build Python services and lead platform reliability.

        Requirements
        - Required Python experience.
        - At least 5 years of professional experience.
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)

    assert _component(result, "experience").score == 100


def test_evidence_v2_marks_unstructured_candidate_tenure_unknown():
    resume = parse_resume_profile(
        """Candidate

        Skills
        Python

        Experience
        Built Python services for production systems.
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Senior Backend Engineer

        Requirements:
        - Required Python experience.

        Experience: 5+ years.
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)
    experience = _component(result, "experience")

    assert experience.status == "unknown"
    assert experience.score is None
    assert experience.effective_weight > 0
    assert experience.contribution == 0
    assert result.score_status == "provisional"


def test_evidence_v2_does_not_attribute_mentee_tenure_to_candidate():
    resume = parse_resume_profile(
        """Candidate

        Skills
        Python

        Experience
        Mentored engineers with 10 years of professional experience while building Python services.
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Senior Backend Engineer

        Requirements:
        - Required Python experience.
        - At least 5 years of professional experience.
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)
    experience = _component(result, "experience")

    assert experience.status == "unknown"
    assert experience.score is None
    assert experience.contribution == 0
    assert result.score_status == "provisional"


def test_evidence_v2_does_not_attribute_collective_tenure_to_candidate():
    resume = parse_resume_profile(
        """Candidate

        Summary
        10 years of professional experience across the engineering team while building services.

        Skills
        Python
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Backend Engineer

        Requirements
        - Required Python experience.
        - At least 5 years of professional experience.
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)

    assert _component(result, "experience").status == "unknown"
    assert result.score_status == "provisional"


@pytest.mark.parametrize(
    "requirement",
    [
        (
            "At least 3 years of professional experience.\n"
            "- A minimum of 5 years of professional experience."
        ),
        "A minimum of five years of professional experience.",
    ],
)
def test_evidence_v2_reserves_weight_for_ambiguous_job_tenure(requirement):
    resume = parse_resume_profile(
        """Candidate

        Skills
        Python

        Projects
        Built Python services for production systems.
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        f"""Role: Backend Engineer

        Requirements
        - Required Python experience.
        - {requirement}
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)
    experience = _component(result, "experience")

    assert job.experience_level == "requirement unclear"
    assert experience.status == "unknown"
    assert experience.effective_weight > 0
    assert experience.contribution == 0
    assert result.score_status == "provisional"


@pytest.mark.parametrize(
    ("candidate_years", "expected_score"),
    [(0, 0), (0.5, 10)],
)
def test_evidence_v2_does_not_grant_synthetic_minimum_tenure_credit(
    candidate_years,
    expected_score,
):
    resume = parse_resume_profile(
        f"""Candidate

        Summary
        {candidate_years:g} years of professional experience.

        Skills
        Python
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Backend Engineer

        Requirements:
        - Required Python experience.
        - At least 5 years of professional experience.
        """,
        job_id=1,
    )

    result = match_resume_to_job(resume, job)

    assert _component(result, "experience").score == expected_score


def test_unknown_tenure_cannot_outscore_explicit_underqualification():
    job = parse_job_profile(
        """Role: Backend Engineer

        Responsibilities:
        - Build Python services and lead platform reliability.

        Requirements:
        - Required Python experience.

        At least 5 years of experience.
        """,
        job_id=1,
    )
    unknown = parse_resume_profile(
        """Candidate

        Skills
        Python

        Experience
        Built Python services and led platform reliability.
        """,
        resume_id=1,
    )
    explicit_junior = parse_resume_profile(
        """Candidate

        Summary
        1 year of professional experience.

        Skills
        Python

        Experience
        Built Python services and led platform reliability.
        """,
        resume_id=2,
    )

    unknown_result = match_resume_to_job(unknown, job)
    junior_result = match_resume_to_job(explicit_junior, job)

    assert job.experience_level == "5 years"
    assert _component(unknown_result, "experience").status == "unknown"
    assert unknown_result.score_status == "provisional"
    assert _component(junior_result, "experience").score == 20
    assert junior_result.score > unknown_result.score


def test_unknown_tenure_reserves_weight_at_zero_on_a_low_baseline():
    job = parse_job_profile(
        """Role: Backend Engineer

        Requirements:
        - Required Python experience.

        At least 5 years of experience.
        """,
        job_id=1,
    )
    unknown = parse_resume_profile(
        """Candidate

        Skills
        Python
        """,
        resume_id=1,
    )
    explicit_junior = parse_resume_profile(
        """Candidate

        Summary
        1 year of professional experience.

        Skills
        Python
        """,
        resume_id=2,
    )

    unknown_result = match_resume_to_job(unknown, job)
    junior_result = match_resume_to_job(explicit_junior, job)
    unknown_experience = _component(unknown_result, "experience")

    assert unknown_experience.status == "unknown"
    assert unknown_experience.effective_weight > 0
    assert unknown_experience.contribution == 0
    assert junior_result.score > unknown_result.score


def test_score_breakdown_honors_an_explicit_zero_cap(sample_resume_text, sample_job_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    result = match_resume_to_job(resume, job)
    assert result.score_breakdown is not None

    payload = result.score_breakdown.model_dump(mode="json")
    payload.update({"score_cap": 0, "score_status": "provisional", "total_score": 0})

    breakdown = MatchScoreBreakdown.model_validate(payload)
    assert breakdown.total_score == 0


def test_score_breakdown_rejects_tampered_effective_weights(
    sample_resume_text,
    sample_job_text,
):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    result = match_resume_to_job(resume, job)
    assert result.score_breakdown is not None

    payload = result.score_breakdown.model_dump(mode="json")
    evidence_strength = next(
        component for component in payload["components"] if component["key"] == "evidence_strength"
    )
    diagnostic_contribution = round((evidence_strength["score"] or 0) * 0.1, 2)
    evidence_strength["effective_weight"] = 10
    evidence_strength["contribution"] = diagnostic_contribution
    payload["uncapped_score"] = round(payload["uncapped_score"] + diagnostic_contribution, 2)
    payload["total_score"] = round(payload["total_score"] + diagnostic_contribution, 2)

    with pytest.raises(ValueError, match="effective weight is inconsistent"):
        MatchScoreBreakdown.model_validate(payload)


def test_deterministic_v1_remains_available_for_queued_pre_upgrade_work():
    resume = parse_resume_profile(
        """Candidate

        Summary
        10 years of professional experience.

        Skills
        Python

        Projects
        Maintained an ongoing Python service.
        """,
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Senior Go Engineer

        Responsibilities:
        - Go ownership delivery excellence.

        Requirements:
        - Required Python experience.

        Experience: 5+ years.
        """,
        job_id=1,
    )

    result = match_resume_to_job(
        resume,
        job,
        scoring_version=DETERMINISTIC_V1_SCORING_VERSION,
    )

    assert result.scoring_version == DETERMINISTIC_V1_SCORING_VERSION
    assert result.experience_level_score == 35
    assert result.responsibility_alignment_score > 0
    assert result.score_breakdown is None


def _component(result, key: str):
    assert result.score_breakdown is not None
    return next(
        component for component in result.score_breakdown.components if component.key == key
    )

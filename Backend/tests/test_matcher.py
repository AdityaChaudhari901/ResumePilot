from app.services.job_parser import parse_job_profile
from app.services.matcher import match_resume_to_job
from app.services.resume_parser import parse_resume_profile


def test_matcher_scores_required_and_missing_skills(sample_resume_text, sample_job_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)

    result = match_resume_to_job(resume, job)

    matched = {skill.skill for skill in result.matched_skills}
    missing = {skill.skill for skill in result.missing_skills}
    assert {"Python", "FastAPI", "REST API"} <= matched
    assert "Docker" in missing
    assert result.score >= 70
    assert all(skill.resume_evidence_ids for skill in result.matched_skills)


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

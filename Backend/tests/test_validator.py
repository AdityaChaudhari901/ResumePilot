from app.schemas.report import ApplicationReport, InterviewQuestionGroup, TailoredBullet
from app.services.job_parser import parse_job_profile
from app.services.matcher import match_resume_to_job
from app.services.report_generator import generate_report
from app.services.resume_parser import parse_resume_profile
from app.services.validator import validate_report_against_resume


def test_validator_flags_tailored_bullet_with_unknown_evidence(sample_resume_text, sample_job_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    report = generate_report(analysis_id=1, resume=resume, job=job, match=match)
    report.tailored_bullets.append(
        TailoredBullet(
            bullet="Built a Docker platform.",
            evidence_ids=["missing_001"],
            jd_keywords_used=[],
            unsupported_claims=[],
        )
    )

    warnings = validate_report_against_resume(report, resume)

    assert {warning.code for warning in warnings} >= {
        "bullet_missing_evidence",
        "bullet_has_unsupported_skill",
    }


def test_report_schema_rejects_empty_cover_letter(sample_resume_text, sample_job_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    report = generate_report(analysis_id=1, resume=resume, job=job, match=match)
    payload = report.model_dump()
    payload["cover_letter"] = ""

    try:
        ApplicationReport.model_validate(payload)
    except Exception as exc:
        assert "cover_letter" in str(exc)
    else:
        raise AssertionError("Expected empty cover letter to fail schema validation")


def test_validator_flags_cover_letter_with_unsupported_skill(sample_resume_text, sample_job_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    report = generate_report(analysis_id=1, resume=resume, job=job, match=match)
    report.cover_letter += "\n\nI also have production Docker experience."

    warnings = validate_report_against_resume(report, resume)

    assert "cover_letter_has_unsupported_skill" in {warning.code for warning in warnings}


def test_validator_flags_unknown_interview_answer_evidence(sample_resume_text, sample_job_text):
    resume = parse_resume_profile(sample_resume_text, resume_id=1)
    job = parse_job_profile(sample_job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    report = generate_report(analysis_id=1, resume=resume, job=job, match=match)
    report.interview_questions.append(
        InterviewQuestionGroup(
            category="Behavioral",
            questions=["Tell me about a time you improved reliability."],
            suggested_answer_evidence_ids=["missing_001"],
        )
    )

    warnings = validate_report_against_resume(report, resume)

    assert "interview_answer_missing_evidence" in {warning.code for warning in warnings}

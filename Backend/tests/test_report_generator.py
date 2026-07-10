from app.services.agent_workflow import run_application_agent_workflow
from app.services.job_parser import parse_job_profile
from app.services.matcher import match_resume_to_job
from app.services.report_generator import report_to_markdown
from app.services.resume_parser import parse_resume_profile
from app.services.validator import validate_report_against_resume

FRAGMENTED_RESUME_TEXT = "\n".join(
    [
        "Aditya Chaudhari",
        "aditya@example.com",
        "",
        "Summary",
        "requirements through testing to production. Comfortable across the stack: React, "
        "Next.js, and React Native on the frontend; Python.",
        "(FastAPI, Flask) and Node.js REST APIs on the backend; SQL and NoSQL databases; "
        "and containerized cloud deployment. Strong in.",
        "",
        "Skills",
        "Python, FastAPI, Flask, SQL, React, Next.js, Git",
        "",
        "Projects",
        "Built a Python FastAPI REST API for a job application tracker with PostgreSQL "
        "and SQLAlchemy.",
        "Implemented a Next.js dashboard for application matching workflows with React "
        "and TypeScript.",
        "",
        "Education",
        "B.Tech Computer Science",
    ]
)


FORBES_STYLE_JOB_TEXT = """Role: Associate Software Engineer
Company: Forbes Advisor

Requirements:
- Required Python experience.
- Required FastAPI or Flask experience.
- Required SQL database experience.
- Required Redis-based job queue experience with Celery or RQ.
- Preferred React or Next.js experience.

Responsibilities:
- Build REST APIs for LLM-powered publishing workflows.
- Maintain background jobs and data integrations.
"""


SKILLS_ONLY_RESUME_TEXT = """Aditya Chaudhari
aditya@example.com

Skills
Python, FastAPI, SQL, React

Education
B.Tech Computer Science
"""


PDF_WRAPPED_RESUME_TEXT = """Aditya Chaudhari
aditya@example.com

Summary
Built web products and APIs using Python and FastAPI.

Skills
Python, FastAPI, PostgreSQL, SQLAlchemy, Pytest

Projects
• Built a job-tracking REST API with Python and
  FastAPI, PostgreSQL, and SQLAlchemy for reliable application workflows.
• Implemented pytest coverage for API failure paths and validation.
"""


DANGLING_PROJECT_FACT_RESUME_TEXT = """Aditya Chaudhari
aditya@example.com

Skills
Python, FastAPI

Projects
Built a Python FastAPI service with
"""


UNCLEAR_REQUIREMENTS_JOB_TEXT = """Persistent careers

Join our engineering team and collaborate with product teams on customer-facing software.
You will improve internal workflows, contribute to platform quality, and communicate with
stakeholders across delivery teams. This listing describes the team and culture, but it does
not expose explicit required or preferred technical skills in readable page text.
"""


def test_tailored_bullets_prefer_project_evidence_over_parser_fragments():
    report, resume = _build_report(FRAGMENTED_RESUME_TEXT, FORBES_STYLE_JOB_TEXT)

    assert report.tailored_bullets
    assert all(bullet.evidence_ids[0].startswith("projects_") for bullet in report.tailored_bullets)
    assert all(
        not bullet.bullet.startswith(("(", ",", ";", ":")) for bullet in report.tailored_bullets
    )
    assert all("Strong in." not in bullet.bullet for bullet in report.tailored_bullets)
    assert all(bullet.bullet.endswith(".") for bullet in report.tailored_bullets)
    assert not validate_report_against_resume(report, resume)


def test_missing_queue_skills_remain_add_only_if_true():
    report, _resume = _build_report(FRAGMENTED_RESUME_TEXT, FORBES_STYLE_JOB_TEXT)

    missing_by_name = {item.skill: item for item in report.missing_skills}

    assert {"Redis", "Celery", "RQ"} <= set(missing_by_name)
    for skill in ("Redis", "Celery", "RQ"):
        recommendation = missing_by_name[skill].recommendation
        assert f"Do not add {skill}" in recommendation
        assert "project or work evidence" in recommendation


def test_skills_only_matches_do_not_create_exportable_tailored_bullets():
    report, resume = _build_report(SKILLS_ONLY_RESUME_TEXT, FORBES_STYLE_JOB_TEXT)

    assert report.weak_skills
    assert report.tailored_bullets == []
    assert not validate_report_against_resume(report, resume)


def test_tailored_bullets_use_reconstructed_project_evidence():
    report, resume = _build_report(PDF_WRAPPED_RESUME_TEXT, FORBES_STYLE_JOB_TEXT)

    assert report.tailored_bullets
    assert report.tailored_bullets[0].bullet == (
        "Built a job-tracking REST API with Python and FastAPI, PostgreSQL, and "
        "SQLAlchemy for reliable application workflows."
    )
    assert report.tailored_bullets[0].evidence_ids == ["projects_001"]
    assert all(
        not bullet.evidence_ids[0].startswith(("summary_", "skills_"))
        for bullet in report.tailored_bullets
    )
    assert not validate_report_against_resume(report, resume)


def test_dangling_project_fact_is_not_promoted_to_tailored_bullet():
    report, resume = _build_report(DANGLING_PROJECT_FACT_RESUME_TEXT, FORBES_STYLE_JOB_TEXT)

    assert report.tailored_bullets == []
    assert {skill.skill for skill in report.matched_skills} >= {"Python", "FastAPI"}
    assert not validate_report_against_resume(report, resume)


def test_unclear_job_requirements_produce_low_confidence_report():
    report, _resume = _build_report(FRAGMENTED_RESUME_TEXT, UNCLEAR_REQUIREMENTS_JOB_TEXT)
    markdown = report_to_markdown(report)

    assert report.match_score <= 25
    assert report.matched_skills == []
    assert report.missing_skills == []
    assert "cannot calculate a trustworthy fit" in report.executive_summary
    assert "direct public job-detail URL" in report.next_actions[0]
    assert "job requirements were not extracted clearly" in report.cover_letter
    assert "Missing skills cannot be determined" in markdown
    assert "No ATS keywords were extracted" in markdown


def _build_report(resume_text: str, job_text: str):
    resume = parse_resume_profile(resume_text, resume_id=1)
    job = parse_job_profile(job_text, job_id=1)
    match = match_resume_to_job(resume, job)
    workflow = run_application_agent_workflow(
        analysis_id=1,
        resume=resume,
        job=job,
        match=match,
    )
    return workflow.report, resume

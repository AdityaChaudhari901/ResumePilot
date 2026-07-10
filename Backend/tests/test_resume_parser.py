from app.services.resume_parser import parse_resume_profile


def test_resume_parser_extracts_candidate_facts_and_skills(sample_resume_text):
    profile = parse_resume_profile(sample_resume_text, resume_id=1)

    assert profile.candidate.name == "Aarav Sharma"
    assert str(profile.candidate.email) == "aarav@example.com"
    assert profile.facts
    skill_names = {skill.name for skill in profile.skills}
    assert {"Python", "FastAPI", "PostgreSQL", "REST API", "Pytest"} <= skill_names
    assert any(fact.section == "projects" for fact in profile.facts)


def test_resume_parser_reconstructs_pdf_wrapped_project_bullets():
    profile = parse_resume_profile(
        """Aarav Sharma
aarav@example.com

Skills
Python, FastAPI, PostgreSQL, SQLAlchemy, Pytest

Projects
• Built a job-tracking REST API with Python and
  FastAPI, PostgreSQL, and SQLAlchemy for reliable application workflows.
• Implemented pytest coverage for API failure paths and validation.
""",
        resume_id=1,
    )

    assert [fact.text for fact in profile.projects] == [
        (
            "Built a job-tracking REST API with Python and FastAPI, PostgreSQL, and "
            "SQLAlchemy for reliable application workflows."
        ),
        "Implemented pytest coverage for API failure paths and validation.",
    ]
    fastapi_skill = next(skill for skill in profile.skills if skill.name == "FastAPI")
    assert "projects_001" in fastapi_skill.evidence_ids


def test_resume_parser_keeps_distinct_unmarked_action_led_facts():
    profile = parse_resume_profile(
        """Aarav Sharma
aarav@example.com

Projects
Built an API using Python and FastAPI
Implemented integration tests using Pytest
""",
        resume_id=1,
    )

    assert [fact.text for fact in profile.projects] == [
        "Built an API using Python and FastAPI",
        "Implemented integration tests using Pytest",
    ]

from app.services.resume_parser import parse_resume_profile


def test_resume_parser_extracts_candidate_facts_and_skills(sample_resume_text):
    profile = parse_resume_profile(sample_resume_text, resume_id=1)

    assert profile.candidate.name == "Aarav Sharma"
    assert str(profile.candidate.email) == "aarav@example.com"
    assert profile.facts
    skill_names = {skill.name for skill in profile.skills}
    assert {"Python", "FastAPI", "PostgreSQL", "REST API", "Pytest"} <= skill_names
    assert any(fact.section == "projects" for fact in profile.facts)

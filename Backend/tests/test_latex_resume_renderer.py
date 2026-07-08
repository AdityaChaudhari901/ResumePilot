from app.services.job_parser import parse_job_profile
from app.services.latex_resume_renderer import render_tailored_resume_latex
from app.services.matcher import match_resume_to_job
from app.services.report_generator import generate_report
from app.services.resume_parser import parse_resume_profile


def test_latex_renderer_escapes_text_and_excludes_missing_skills():
    resume = parse_resume_profile(
        """A&B_Dev
a.dev@example.com
https://github.com/A_B?x=1&y=2

Skills
Python, FastAPI

Projects
Built FastAPI_API services & improved reliability by 40%.
""",
        resume_id=1,
    )
    job = parse_job_profile(
        """Role: Platform Engineer
Company: Example Labs

Requirements:
- Required Python experience.
- Required FastAPI experience.
- Required Kubernetes experience.
""",
        job_id=1,
    )
    match = match_resume_to_job(resume, job)
    report = generate_report(analysis_id=1, resume=resume, job=job, match=match)

    latex = render_tailored_resume_latex(report=report, resume=resume, job=job)

    assert r"A\&B\_Dev" in latex
    assert r"FastAPI\_API services \& improved reliability by 40\%" in latex
    assert "A&B_Dev" not in latex
    assert "Built FastAPI_API services & improved reliability by 40%." not in latex
    assert "Kubernetes" not in latex

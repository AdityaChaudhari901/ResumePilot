import pytest
from fastapi import HTTPException

from app.services.job_parser import fetch_job_text, parse_job_profile


class FakeResponse:
    def __init__(self, *, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("request failed")


def test_fetch_job_text_rejects_blocked_pages(monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: FakeResponse(status_code=403, text="blocked"),
    )

    with pytest.raises(HTTPException) as exc_info:
        fetch_job_text("https://example.com/jobs/1")

    assert exc_info.value.status_code == 422
    assert "Paste the job description" in exc_info.value.detail


def test_job_parser_marks_required_skill_missing_candidate(sample_job_text):
    profile = parse_job_profile(sample_job_text, job_id=1)

    required = {skill.name for skill in profile.required_skills}
    assert {"Python", "FastAPI", "REST API", "SQL"} <= required

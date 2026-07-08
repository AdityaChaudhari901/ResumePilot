import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.job_parser import fetch_job_text, parse_job_profile


class FakeResponse:
    def __init__(self, *, status_code: int = 200, text: str = "") -> None:
        self.status_code = status_code
        self.text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("request failed")


def test_fetch_job_text_rejects_blocked_pages(monkeypatch):
    fallback_called = False

    def fake_browser_fallback(*args, **kwargs):
        nonlocal fallback_called
        fallback_called = True
        return "Rendered text should not be used for blocked pages."

    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: FakeResponse(status_code=403, text="blocked"),
    )
    monkeypatch.setattr(
        "app.services.job_parser._fetch_job_text_with_playwright",
        fake_browser_fallback,
    )

    with pytest.raises(HTTPException) as exc_info:
        fetch_job_text("https://example.com/jobs/1", settings=Settings())

    assert exc_info.value.status_code == 422
    assert "Paste the job description" in exc_info.value.detail
    assert fallback_called is False


def test_fetch_job_text_uses_playwright_fallback_for_short_public_pages(monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: FakeResponse(
            status_code=200,
            text="<html><body><div id='root'></div><script>render()</script></body></html>",
        ),
    )
    monkeypatch.setattr(
        "app.services.job_parser._fetch_job_text_with_playwright",
        lambda *args, **kwargs: (
            "Role: Backend Engineer\n"
            "Company: Rendered Labs\n"
            "Requirements: Required Python and FastAPI experience."
        ),
    )

    text = fetch_job_text("https://example.com/jobs/2", settings=Settings())

    assert "Rendered Labs" in text
    assert "FastAPI" in text


def test_fetch_job_text_returns_paste_fallback_when_browser_rendering_is_unavailable(
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: FakeResponse(status_code=200, text="<html></html>"),
    )
    monkeypatch.setattr(
        "app.services.job_parser._fetch_job_text_with_playwright",
        lambda *args, **kwargs: "",
    )

    with pytest.raises(HTTPException) as exc_info:
        fetch_job_text("https://example.com/jobs/3", settings=Settings())

    assert exc_info.value.status_code == 422
    assert "Playwright Chromium browser" in exc_info.value.detail


def test_job_parser_marks_required_skill_missing_candidate(sample_job_text):
    profile = parse_job_profile(sample_job_text, job_id=1)

    required = {skill.name for skill in profile.required_skills}
    assert {"Python", "FastAPI", "REST API", "SQL"} <= required

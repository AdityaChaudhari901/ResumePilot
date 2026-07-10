import pytest
from fastapi import HTTPException

from app.core.config import Settings
from app.services.job_parser import JobParseError, fetch_job_text, parse_job_profile


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        text: str = "",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode()
        self.encoding = "utf-8"
        self.headers = headers or {"content-type": "text/html"}
        self.raw = None

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("request failed")

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.content

    def close(self) -> None:
        return None


@pytest.fixture(autouse=True)
def public_job_url(monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser._assert_public_job_url",
        lambda _url: frozenset(),
    )
    monkeypatch.setattr(
        "app.services.job_parser._assert_public_peer",
        lambda _response, _allowed_ips: None,
    )


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


def test_fetch_job_text_rejects_private_and_credentialed_urls(monkeypatch):
    monkeypatch.undo()
    from app.services.job_parser import _assert_public_job_url

    for job_url in (
        "http://127.0.0.1/admin",
        "http://169.254.169.254/latest/meta-data",
        "http://user:secret@example.com/jobs/1",
        "file:///etc/passwd",
    ):
        with pytest.raises(Exception, match="private|credentials|public HTTP"):
            _assert_public_job_url(job_url)


def test_fetch_job_text_validates_redirect_target(monkeypatch):
    responses = [FakeResponse(status_code=302, headers={"location": "http://127.0.0.1/admin"})]
    checked_urls: list[str] = []

    def validate_url(url: str):
        checked_urls.append(url)
        if "127.0.0.1" in url:
            raise JobParseError("private redirect")
        return frozenset()

    monkeypatch.setattr("app.services.job_parser._assert_public_job_url", validate_url)
    monkeypatch.setattr(
        "app.services.job_parser.requests.get", lambda *args, **kwargs: responses.pop(0)
    )

    with pytest.raises(HTTPException, match="private redirect"):
        fetch_job_text("https://example.com/jobs/redirect")

    assert checked_urls == ["https://example.com/jobs/redirect", "http://127.0.0.1/admin"]


def test_fetch_job_text_rejects_oversized_response(monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: FakeResponse(
            headers={
                "content-length": str(2 * 1024 * 1024 + 1),
                "content-type": "text/html",
            }
        ),
    )

    with pytest.raises(HTTPException) as exc_info:
        fetch_job_text("https://example.com/jobs/large")

    assert exc_info.value.status_code == 422
    assert "too large" in exc_info.value.detail


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


def test_fetch_job_text_prefers_json_ld_job_posting(monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: FakeResponse(
            status_code=200,
            text="""<html><body>
            <script type="application/ld+json">
            {
              "@type": "JobPosting",
              "title": "Platform Engineer",
              "hiringOrganization": {"name": "Schema Labs"},
              "description": "<p>Required Python and FastAPI experience.</p>"
            }
            </script>
            <nav>Marketing navigation should not dominate extraction.</nav>
            </body></html>""",
        ),
    )

    text = fetch_job_text("https://boards.greenhouse.io/schema/jobs/1", settings=Settings())
    profile = parse_job_profile(text, job_id=1)

    assert profile.role_title == "Platform Engineer"
    assert profile.company == "Schema Labs"
    assert {"Python", "FastAPI"} <= {skill.name for skill in profile.required_skills}


def test_job_parser_marks_required_skill_missing_candidate(sample_job_text):
    profile = parse_job_profile(sample_job_text, job_id=1)

    required = {skill.name for skill in profile.required_skills}
    assert {"Python", "FastAPI", "REST API", "SQL"} <= required


def test_job_parser_detects_hyphenated_and_slash_separated_skills():
    profile = parse_job_profile(
        """Role: Associate Software Engineer
Company: Forbes Advisor

Requirements:
- Required Redis-based job queues with Celery/RQ.
- Preferred JavaScript/TypeScript and React/Next.js experience.
""",
        job_id=1,
    )

    required = {skill.name for skill in profile.required_skills}
    preferred = {skill.name for skill in profile.preferred_skills}

    assert {"Redis", "Celery", "RQ"} <= required
    assert {"JavaScript", "TypeScript", "React", "Next.js"} <= preferred


def test_job_parser_does_not_carry_required_context_into_responsibilities():
    profile = parse_job_profile(
        """Role: Associate Software Engineer
Company: Forbes Advisor

Requirements:
- Required Python experience.

Responsibilities:
- Build REST APIs for LLM-powered publishing workflows.
""",
        job_id=1,
    )

    required = {skill.name for skill in profile.required_skills}
    keywords = set(profile.keywords)

    assert required == {"Python"}
    assert "LLM" in keywords

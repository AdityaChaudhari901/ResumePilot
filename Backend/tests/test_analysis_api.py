import pytest
from sqlalchemy import select

from app.db.models import AnalysisRecord, UserRecord
from app.schemas.agent import AgentStepName, AgentWorkflowMode
from tests.api_helpers import successful_analysis


@pytest.fixture(autouse=True)
def public_job_fetch(monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser._assert_public_job_url",
        lambda _url: frozenset(),
    )
    monkeypatch.setattr(
        "app.services.job_parser._assert_public_peer",
        lambda _response, _allowed_ips: None,
    )


def test_job_preview_parses_public_url_without_creating_report(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: _FakeJobFetchResponse(
            text="""<html><body>
            <h1>Backend Engineer</h1>
            <p>Company: NovaHire AI</p>
            <h2>Requirements</h2>
            <p>Required Python experience.</p>
            <p>Required FastAPI experience.</p>
            <p>Preferred Pytest experience.</p>
            <h2>Responsibilities</h2>
            <p>Build REST APIs for hiring workflows.</p>
            </body></html>"""
        ),
    )

    response = client.post(
        "/jobs/preview",
        json={"job_url": "https://example.com/jobs/backend-engineer"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["profile"]["role_title"] == "Backend Engineer"
    assert body["profile"]["company"] == "NovaHire AI"
    assert {skill["name"] for skill in body["profile"]["required_skills"]} >= {
        "Python",
        "FastAPI",
    }
    assert {skill["name"] for skill in body["profile"]["preferred_skills"]} >= {"Pytest"}
    assert body["raw_text_char_count"] > 40

    history_response = client.get("/reports")
    assert history_response.status_code == 200
    assert history_response.json()["items"] == []


def test_job_preview_marks_unclear_requirements_for_review(client, monkeypatch):
    monkeypatch.setattr(
        "app.services.job_parser.requests.get",
        lambda *args, **kwargs: _FakeJobFetchResponse(
            text="""<html><body>
            <h1>Persistent Careers</h1>
            <p>Join our engineering team and collaborate with product teams.</p>
            <p>This public page describes culture but exposes no explicit skill requirements.</p>
            </body></html>"""
        ),
    )

    response = client.post(
        "/jobs/preview",
        json={"job_url": "https://example.com/jobs/unclear"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "missing_requirements"
    assert body["profile"]["required_skills"] == []
    assert "required_skills_unclear" in {warning["code"] for warning in body["profile"]["warnings"]}
    assert any(check["code"] == "required_or_preferred_skills" for check in body["quality_checks"])


@pytest.mark.parametrize(
    ("filename", "content", "content_type", "expected_detail"),
    [
        ("resume.pdf", b"not a pdf", "application/pdf", "valid PDF signature"),
        (
            "resume.docx",
            b"not an office archive",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "valid Office document",
        ),
        ("resume.txt", b"Aarav\x00Sharma", "text/plain", "invalid binary data"),
    ],
)
def test_resume_upload_rejects_mismatched_or_unsafe_content(
    client,
    settings,
    filename,
    content,
    content_type,
    expected_detail,
):
    response = client.post(
        "/resumes/upload",
        files={"file": (filename, content, content_type)},
    )

    assert response.status_code == 400
    assert expected_detail in response.json()["detail"]
    assert list(settings.upload_dir.glob("users/*/*")) == []


def test_resume_upload_does_not_persist_a_pdf_that_fails_parsing(client, settings):
    response = client.post(
        "/resumes/upload",
        files={"file": ("resume.pdf", b"%PDF-invalid", "application/pdf")},
    )

    assert response.status_code == 422
    assert list(settings.upload_dir.glob("users/*/*")) == []


def test_analyze_uses_reviewed_job_profile_without_refetching(
    client, monkeypatch, sample_resume_text
):
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
    )
    assert upload_response.status_code == 201
    resume_id = upload_response.json()["resume_id"]
    reviewed_profile = {
        "benefits": [],
        "company": "Reviewed Labs",
        "employment_type": None,
        "experience_level": "0-2 years",
        "job_id": 0,
        "keywords": ["Python", "FastAPI"],
        "location": None,
        "preferred_skills": [],
        "required_skills": [
            {
                "confidence": "high",
                "evidence_text": "Required Python experience.",
                "id": "job_required_001",
                "importance": "required",
                "name": "Python",
            },
            {
                "confidence": "high",
                "evidence_text": "Required FastAPI experience.",
                "id": "job_required_002",
                "importance": "required",
                "name": "FastAPI",
            },
        ],
        "responsibilities": ["Build REST APIs for reviewed workflows."],
        "role_title": "Reviewed Backend Engineer",
        "unclear_items": [],
        "warnings": [],
    }
    reviewed_text = (
        "Role: Reviewed Backend Engineer\nCompany: Reviewed Labs\n\n"
        "Requirements:\n- Required Python experience.\n- Required FastAPI experience.\n\n"
        "Responsibilities:\n- Build REST APIs for reviewed workflows."
    )
    application_response = client.post(
        "/applications",
        json={
            "source_type": "url",
            "job_url": "https://example.com/jobs/reviewed",
            "reviewed_job_text": reviewed_text,
            "reviewed_job_profile": reviewed_profile,
            "resume_id": resume_id,
        },
    )
    assert application_response.status_code == 201

    def fail_fetch(*args, **kwargs):
        raise AssertionError("analysis should use reviewed_job_profile instead of refetching")

    monkeypatch.setattr("app.services.analysis_service.fetch_job_text", fail_fetch)

    body = successful_analysis(
        client,
        {
            "resume_id": resume_id,
            "application_id": application_response.json()["id"],
        },
    )

    report_response = client.get(f"/reports/{body['report_id']}")
    assert report_response.status_code == 200
    report = report_response.json()
    assert {skill["skill"] for skill in report["matched_skills"]} >= {"Python", "FastAPI"}

    history_response = client.get("/reports")
    assert history_response.status_code == 200
    item = history_response.json()["items"][0]
    assert item["company"] == "Reviewed Labs"
    assert item["role"] == "Reviewed Backend Engineer"


def test_upload_analyze_and_read_report(client, sample_resume_text, sample_job_text):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    assert body["status"] == "completed"
    assert 60 <= body["match_score"] < 75
    assert body["scoring_version"] == "evidence_v2"
    assert body["score_status"] == "scored"

    history_response = client.get("/reports")
    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history["items"]) == 1
    history_item = history["items"][0]
    assert history_item["report_id"] == body["report_id"]
    assert history_item["analysis_id"] == body["analysis_id"]
    assert history_item["resume_id"] == body["resume_id"]
    assert history_item["company"] == "NovaHire AI"
    assert history_item["role"] == "Junior Backend Engineer"
    assert history_item["resume_candidate_name"] == "Aarav Sharma"
    assert history_item["matched_skills_count"] >= 1
    assert history_item["scoring_version"] == "evidence_v2"
    assert history_item["score_status"] == "scored"
    assert history_item["created_at"]

    resume_response = client.get(f"/resumes/{body['resume_id']}")
    assert resume_response.status_code == 200
    resume = resume_response.json()
    assert resume["resume_id"] == body["resume_id"]
    assert resume["candidate"]["name"] == "Aarav Sharma"
    assert resume["skills"]
    assert resume["facts"]

    report_response = client.get(f"/reports/{body['report_id']}")
    assert report_response.status_code == 200
    report = report_response.json()
    assert report["analysis_id"] == body["analysis_id"]
    assert report["scoring_version"] == "evidence_v2"
    assert report["score_status"] == "scored"
    assert report["score_breakdown"]["total_score"] == report["match_score"]
    assert {component["key"] for component in report["score_breakdown"]["components"]} == {
        "required_skills",
        "responsibilities",
        "preferred_skills",
        "experience",
        "domain",
        "evidence_strength",
    }
    assert report["tailored_bullets"]
    assert all(item["evidence_ids"] for item in report["tailored_bullets"])

    markdown_response = client.post(f"/reports/{body['report_id']}/markdown")
    assert markdown_response.status_code == 200
    assert "# Job Fit Report" in markdown_response.text
    assert "not a hiring probability or ATS guarantee" in markdown_response.text

    with client.app.state.session_factory() as db:
        stored = db.get(AnalysisRecord, body["analysis_id"])
        assert stored is not None
        assert stored.scoring_version == "evidence_v2"
        assert stored.score_status == "scored"
        assert stored.score_breakdown_json["total_score"] == stored.match_score
        assert "scoring_version" not in stored.report_json
        assert "score_status" not in stored.report_json
        assert "score_breakdown" not in stored.report_json
        assert "scoring_version" not in stored.match_result_json
        assert "score_status" not in stored.match_result_json
        assert "score_breakdown" not in stored.match_result_json

    for export_format in ("latex", "docx", "pdf"):
        response = client.post(f"/reports/{body['report_id']}/resume/{export_format}")
        assert response.status_code == 404

    trace_response = client.get(f"/reports/{body['report_id']}/trace")
    assert trace_response.status_code == 200
    trace_body = trace_response.json()
    assert trace_body["analysis_id"] == body["analysis_id"]
    assert trace_body["report_id"] == body["report_id"]
    assert trace_body["trace"]["mode"] == AgentWorkflowMode.deterministic_fallback
    assert [step["name"] for step in trace_body["trace"]["steps"]] == [
        AgentStepName.jd_parser,
        AgentStepName.resume_match,
        AgentStepName.ats_optimizer,
        AgentStepName.cover_letter,
        AgentStepName.interview_coach,
        AgentStepName.validation_gate,
    ]
    assert isinstance(trace_body["trace"]["duration_ms"], int)
    assert all(isinstance(step["duration_ms"], int) for step in trace_body["trace"]["steps"])
    assert trace_body["trace"]["provider"] is None
    assert trace_body["trace"]["model"] is None
    assert trace_body["trace"]["token_usage"] is None
    assert trace_body["trace"]["cost_estimate_usd"] is None
    assert trace_body["trace"]["runtime_metadata"] == {}


def test_legacy_report_is_labeled_without_mutating_historical_json(
    client,
    sample_resume_text,
    sample_job_text,
):
    body = _upload_and_analyze(client, sample_resume_text, sample_job_text)
    with client.app.state.session_factory() as db:
        analysis = db.get(AnalysisRecord, body["analysis_id"])
        assert analysis is not None
        historical_json = dict(analysis.report_json)
        analysis.scoring_version = "legacy_unversioned"
        analysis.score_status = "scored"
        analysis.score_breakdown_json = None
        db.commit()

    response = client.get(f"/reports/{body['report_id']}")

    assert response.status_code == 200
    report = response.json()
    assert report["match_score"] == body["match_score"]
    assert report["scoring_version"] == "legacy_unversioned"
    assert report["score_status"] == "scored"
    assert report["score_breakdown"] is None
    with client.app.state.session_factory() as db:
        analysis = db.get(AnalysisRecord, body["analysis_id"])
        assert analysis is not None
        assert analysis.report_json == historical_json


def test_langgraph_fallback_trace_is_persisted(
    client, monkeypatch, sample_resume_text, sample_job_text, settings
):
    settings.agent_workflow_mode = AgentWorkflowMode.langgraph

    class UnavailableRunner:
        def __init__(self, **_kwargs):
            pass

        def start(self, **_kwargs):
            raise RuntimeError("Private provider failure")

    monkeypatch.setattr(
        "app.services.workflow_job_service.LiveDraftGraphRunner",
        UnavailableRunner,
    )

    body = _upload_and_analyze(client, sample_resume_text, sample_job_text, plan="premium")

    report_response = client.get(f"/reports/{body['report_id']}")
    assert report_response.status_code == 200
    warning_codes = [warning["code"] for warning in report_response.json()["validation_warnings"]]
    assert "langgraph_unavailable" in warning_codes

    trace_response = client.get(f"/reports/{body['report_id']}/trace")
    assert trace_response.status_code == 200
    trace = trace_response.json()["trace"]
    assert trace["mode"] == AgentWorkflowMode.deterministic_fallback
    assert trace["steps"][0]["name"] == AgentStepName.langgraph_runtime
    assert trace["steps"][0]["status"] == "failed"
    assert trace["steps"][0]["duration_ms"] is None
    assert isinstance(trace["duration_ms"], int)
    assert trace["provider"] == "vertex"
    assert trace["model"] == "google_genai/gemini-3.5-flash"
    assert trace["token_usage"] is None
    assert trace["cost_estimate_usd"] is None
    assert trace["runtime_metadata"]["runtime_status"] == "failed"
    assert trace["runtime_metadata"]["workflow_runtime"] == "langgraph"
    assert "langgraph_unavailable" in trace["validation_warning_codes"]


def test_premium_plan_does_not_run_live_ai_without_per_analysis_consent(
    client,
    monkeypatch,
    sample_resume_text,
    sample_job_text,
    settings,
):
    settings.agent_workflow_mode = AgentWorkflowMode.langgraph

    class UnexpectedRunner:
        def __init__(self, **_kwargs):
            raise AssertionError("Live AI must not run without explicit analysis consent")

    monkeypatch.setattr(
        "app.services.workflow_job_service.LiveDraftGraphRunner",
        UnexpectedRunner,
    )

    body = _upload_and_analyze(
        client,
        sample_resume_text,
        sample_job_text,
        plan="premium",
        allow_live_ai_processing=False,
    )

    trace = client.get(f"/reports/{body['report_id']}/trace").json()["trace"]
    usage = client.get("/usage/summary").json()
    live_ai_limit = next(item for item in usage["limits"] if item["metric"] == "live_ai_runs")
    assert trace["mode"] == AgentWorkflowMode.deterministic_fallback
    assert live_ai_limit["used"] == 0


def _upload_and_analyze(
    client,
    resume_text: str,
    job_text: str,
    *,
    plan: str = "free",
    allow_live_ai_processing: bool | None = None,
) -> dict:
    upload_response = client.post(
        "/resumes/upload",
        files={"file": ("resume.md", resume_text.encode("utf-8"), "text/markdown")},
    )

    assert upload_response.status_code == 201
    resume_id = upload_response.json()["resume_id"]
    if plan != "free":
        _set_dev_user_plan(client, plan)

    body = successful_analysis(
        client,
        {
            "resume_id": resume_id,
            "job_text": job_text,
            "allow_live_ai_processing": (
                plan == "premium" if allow_live_ai_processing is None else allow_live_ai_processing
            ),
        },
    )
    body["resume_id"] = resume_id
    return body


def _set_dev_user_plan(client, plan: str) -> None:
    with client.app.state.session_factory() as db:
        user = db.scalar(
            select(UserRecord).where(UserRecord.external_id == "local-dev-user").limit(1)
        )
        assert user is not None
        user.plan = plan
        user.subscription_status = "active"
        db.commit()


class _FakeJobFetchResponse:
    status_code = 200

    def __init__(self, text: str) -> None:
        self.text = text
        self.content = text.encode()
        self.encoding = "utf-8"
        self.headers = {"content-type": "text/html"}
        self.raw = None

    def raise_for_status(self) -> None:
        return None

    def iter_content(self, chunk_size: int):
        del chunk_size
        yield self.content

    def close(self) -> None:
        return None

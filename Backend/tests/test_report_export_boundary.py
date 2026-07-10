from app.api.routes import reports
from app.schemas.auth import CurrentUser


def test_generic_report_resume_document_routes_are_not_registered(client):
    registered_paths = set(client.app.openapi()["paths"])

    assert "/reports/{report_id}/resume/latex" not in registered_paths
    assert "/reports/{report_id}/resume/docx" not in registered_paths
    assert "/reports/{report_id}/resume/pdf" not in registered_paths
    assert "/applications/{application_id}/tailored-resume/latex" in registered_paths
    assert "/applications/{application_id}/tailored-resume/docx" in registered_paths
    assert "/applications/{application_id}/tailored-resume/pdf" in registered_paths


def test_markdown_report_export_does_not_advance_application_lifecycle(monkeypatch):
    calls: list[tuple[str, object]] = []

    class FakeSession:
        def commit(self) -> None:
            calls.append(("commit", None))

    current_user = CurrentUser(
        id=7,
        external_id="export-boundary-user",
        plan="free",
        subscription_status="inactive",
    )
    monkeypatch.setattr(
        reports,
        "reserve_export_usage",
        lambda _db, _user, *, report_id, export_format: calls.append(
            ("usage", (report_id, export_format))
        ),
    )
    monkeypatch.setattr(
        reports,
        "add_audit_event",
        lambda _db, *, event_type, user_id, payload: calls.append(
            ("audit", (event_type, user_id, payload))
        ),
    )

    reports._finalize_report_export(
        FakeSession(),
        current_user,
        report_id=42,
        export_format="markdown",
    )

    assert calls == [
        ("usage", (42, "markdown")),
        ("audit", ("report.exported", 7, {"report_id": 42, "format": "markdown"})),
        ("commit", None),
    ]

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.auth_signature import (
    AUTH_SIGNATURE_HEADER,
    AUTH_TIMESTAMP_HEADER,
    sign_identity,
)

AUTH_SECRET = "test-auth-proxy-secret"


def test_auth_required_accepts_signed_identity_headers(settings, sample_resume_text):
    settings.auth_required = True
    settings.auth_trusted_proxy_secret = AUTH_SECRET
    app = create_app(settings)

    with TestClient(app) as auth_client:
        response = auth_client.post(
            "/resumes/upload",
            files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
            headers=_signed_headers(
                external_id="signed-user",
                email="signed@example.com",
                display_name="Signed User",
            ),
        )

    assert response.status_code == 201
    assert response.json()["status"] == "parsed"


def test_auth_required_rejects_raw_unsigned_identity_headers(settings, sample_resume_text):
    settings.auth_required = True
    app = create_app(settings)

    with TestClient(app) as auth_client:
        response = auth_client.post(
            "/resumes/upload",
            files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
            headers={"X-ResumePilot-User": "spoofed-user"},
        )

    assert response.status_code == 503
    assert (
        response.json()["detail"] == "AUTH_TRUSTED_PROXY_SECRET is required when AUTH_REQUIRED=true"
    )


def test_signed_identity_rejects_tampered_user_headers(settings, sample_resume_text):
    settings.auth_required = True
    settings.auth_trusted_proxy_secret = AUTH_SECRET
    app = create_app(settings)
    headers = _signed_headers(
        external_id="signed-user",
        email="signed@example.com",
        display_name="Signed User",
    )
    headers["X-ResumePilot-User"] = "different-user"

    with TestClient(app) as auth_client:
        response = auth_client.post(
            "/resumes/upload",
            files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
            headers=headers,
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authenticated user signature"


def test_signed_identity_rejects_expired_timestamp(settings, sample_resume_text):
    settings.auth_required = True
    settings.auth_trusted_proxy_secret = AUTH_SECRET
    app = create_app(settings)
    timestamp = str(int((datetime.now(UTC) - timedelta(minutes=20)).timestamp()))

    with TestClient(app) as auth_client:
        response = auth_client.post(
            "/resumes/upload",
            files={"file": ("resume.md", sample_resume_text.encode("utf-8"), "text/markdown")},
            headers=_signed_headers(
                external_id="signed-user",
                email="signed@example.com",
                display_name="Signed User",
                timestamp=timestamp,
            ),
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authenticated user signature"


def test_signed_identity_cannot_be_replayed_on_a_different_operation(settings):
    settings.auth_required = True
    settings.auth_trusted_proxy_secret = AUTH_SECRET
    app = create_app(settings)

    with TestClient(app) as auth_client:
        response = auth_client.get(
            "/reports",
            headers=_signed_headers(
                external_id="signed-user",
                email="signed@example.com",
                display_name="Signed User",
            ),
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid authenticated user signature"


def _signed_headers(
    *,
    external_id: str,
    email: str,
    display_name: str,
    timestamp: str | None = None,
) -> dict[str, str]:
    timestamp = timestamp or str(int(datetime.now(UTC).timestamp()))
    return {
        "X-ResumePilot-User": external_id,
        "X-ResumePilot-Email": email,
        "X-ResumePilot-Name": display_name,
        AUTH_TIMESTAMP_HEADER: timestamp,
        AUTH_SIGNATURE_HEADER: sign_identity(
            secret=AUTH_SECRET,
            external_id=external_id,
            email=email,
            display_name=display_name,
            timestamp=timestamp,
            method="POST",
            path="/resumes/upload",
        ),
    }

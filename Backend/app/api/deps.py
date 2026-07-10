from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import constant_time_equals, unauthorized
from app.schemas.auth import CurrentUser
from app.services.auth_signature import (
    AUTH_SIGNATURE_HEADER,
    AUTH_TIMESTAMP_HEADER,
    verify_identity_signature,
)
from app.services.identity_service import get_or_create_user

bearer_scheme = HTTPBearer(auto_error=False)
USER_ID_HEADER = "x-resumepilot-user"
USER_EMAIL_HEADER = "x-resumepilot-email"
USER_NAME_HEADER = "x-resumepilot-name"


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Generator[Session, None, None]:
    session_factory = request.app.state.session_factory
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


def require_openclaw_auth(
    settings: Settings = Depends(get_settings),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    if not settings.jobcopilot_api_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JOBCOPILOT_API_TOKEN is not configured",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized()
    if not constant_time_equals(credentials.credentials, settings.jobcopilot_api_token):
        raise unauthorized()


def require_allowed_sender(sender: str, settings: Settings) -> None:
    if settings.openclaw_sender_allowlist and sender not in settings.openclaw_sender_allowlist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Sender is not allowed")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    external_id = _header_value(request, USER_ID_HEADER)
    email = _header_value(request, USER_EMAIL_HEADER)
    display_name = _header_value(request, USER_NAME_HEADER)

    if external_id:
        _verify_authenticated_user_headers(
            request=request,
            settings=settings,
            external_id=external_id,
            email=email,
            display_name=display_name,
        )

    if not external_id:
        if settings.auth_required:
            raise unauthorized("Missing authenticated user context")
        external_id = settings.dev_user_external_id
        email = settings.dev_user_email
        display_name = settings.dev_user_display_name

    if len(external_id) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user identifier is too long",
        )
    if email and len(email) > 320:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user email is too long",
        )
    if display_name and len(display_name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Authenticated user display name is too long",
        )

    return get_or_create_user(
        db,
        external_id=external_id,
        email=email,
        display_name=display_name,
        initial_plan=_initial_plan_for_user(external_id, settings),
        initial_subscription_status=_initial_subscription_status_for_user(external_id, settings),
    )


def _verify_authenticated_user_headers(
    *,
    request: Request,
    settings: Settings,
    external_id: str,
    email: str | None,
    display_name: str | None,
) -> None:
    if settings.auth_trusted_proxy_secret:
        timestamp = _header_value(request, AUTH_TIMESTAMP_HEADER)
        signature = _header_value(request, AUTH_SIGNATURE_HEADER)
        if not verify_identity_signature(
            secret=settings.auth_trusted_proxy_secret,
            external_id=external_id,
            email=email,
            display_name=display_name,
            timestamp=timestamp,
            signature=signature,
            max_age_seconds=settings.auth_signature_ttl_seconds,
            method=request.method,
            path=request.url.path,
        ):
            raise unauthorized("Invalid authenticated user signature")
        return

    if settings.auth_required:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AUTH_TRUSTED_PROXY_SECRET is required when AUTH_REQUIRED=true",
        )


def _header_value(request: Request, header_name: str) -> str | None:
    value = request.headers.get(header_name)
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _initial_plan_for_user(external_id: str, settings: Settings) -> str:
    if _is_configured_dev_user(external_id, settings):
        return settings.dev_user_plan
    return "free"


def _initial_subscription_status_for_user(external_id: str, settings: Settings) -> str:
    if _is_configured_dev_user(external_id, settings):
        return settings.dev_user_subscription_status
    return "inactive"


def _is_configured_dev_user(external_id: str, settings: Settings) -> bool:
    return (
        settings.app_env in {"development", "test"} and external_id == settings.dev_user_external_id
    )

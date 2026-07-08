from collections.abc import Generator

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.security import constant_time_equals, unauthorized

bearer_scheme = HTTPBearer(auto_error=False)


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

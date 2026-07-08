from fastapi import APIRouter, Depends

from app.api.deps import get_settings
from app.core.config import Settings
from app.schemas.common import StrictBaseModel

router = APIRouter(tags=["health"])


class HealthResponse(StrictBaseModel):
    status: str
    app: str
    environment: str


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.app_env)

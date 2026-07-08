from fastapi import APIRouter, Depends, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.api.deps import get_settings
from app.core.config import Settings
from app.schemas.common import StrictBaseModel
from app.services.readiness_service import check_application_readiness

router = APIRouter(tags=["health"])


class HealthResponse(StrictBaseModel):
    status: str
    app: str
    environment: str


class ReadinessCheckResponse(StrictBaseModel):
    name: str
    status: str
    detail: str


class ReadinessResponse(StrictBaseModel):
    status: str
    app: str
    environment: str
    checks: list[ReadinessCheckResponse]


@router.get("/health", response_model=HealthResponse)
def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(status="ok", app=settings.app_name, environment=settings.app_env)


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": ReadinessResponse}},
)
def readiness(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> ReadinessResponse | JSONResponse:
    result = check_application_readiness(request.app.state.engine, settings)
    response = ReadinessResponse(
        status=result.status,
        app=settings.app_name,
        environment=settings.app_env,
        checks=[
            ReadinessCheckResponse(
                name=check.name,
                status=check.status,
                detail=check.detail,
            )
            for check in result.checks
        ],
    )
    if result.status != "ok":
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=jsonable_encoder(response),
        )
    return response

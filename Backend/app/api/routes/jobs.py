from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.core.config import Settings
from app.schemas.auth import CurrentUser
from app.schemas.job import JobAnalysisRequest, JobPreviewRequest, JobPreviewResponse
from app.schemas.operation import WorkflowJobResponse
from app.services.analysis_service import preview_job
from app.services.workflow_job_service import (
    enqueue_analysis_job,
    execute_workflow_job,
    workflow_job_response,
)

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post(
    "/analyze",
    response_model=WorkflowJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def analyze_job_description(
    request: JobAnalysisRequest,
    http_request: Request,
    response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowJobResponse:
    operation, created = enqueue_analysis_job(
        db,
        request,
        current_user,
        idempotency_key=idempotency_key,
        request_id=getattr(http_request.state, "request_id", None),
        max_attempts=settings.workflow_job_max_attempts,
    )
    if created and settings.execute_workflow_jobs_inline:
        operation = execute_workflow_job(
            db,
            operation.id,
            settings=settings,
            worker_id=f"inline-{operation.id}",
        )
    response.headers["Location"] = f"/operations/{operation.id}"
    response.headers["Retry-After"] = "1"
    return workflow_job_response(operation)


@router.post("/preview", response_model=JobPreviewResponse)
def preview_job_listing(
    request: JobPreviewRequest,
    settings: Settings = Depends(get_settings),
    _current_user: CurrentUser = Depends(get_current_user),
) -> JobPreviewResponse:
    return preview_job(request, settings)

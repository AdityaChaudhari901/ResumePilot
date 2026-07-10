from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.core.config import Settings
from app.schemas.auth import CurrentUser
from app.schemas.operation import WorkflowJobListResponse, WorkflowJobResponse
from app.services.workflow_job_service import (
    cancel_workflow_job,
    get_workflow_job,
    get_workflow_job_artifact,
    list_workflow_jobs,
)

router = APIRouter(prefix="/operations", tags=["operations"])


@router.get("", response_model=WorkflowJobListResponse)
def read_operations(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowJobListResponse:
    return list_workflow_jobs(db, current_user, limit=limit)


@router.get("/{operation_id}", response_model=WorkflowJobResponse)
def read_operation(
    operation_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowJobResponse:
    return get_workflow_job(db, operation_id, current_user)


@router.post("/{operation_id}/cancel", response_model=WorkflowJobResponse)
def cancel_operation(
    operation_id: str,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> WorkflowJobResponse:
    return cancel_workflow_job(db, operation_id, current_user)


@router.get("/{operation_id}/artifact")
def download_operation_artifact(
    operation_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> FileResponse:
    path, filename, media_type = get_workflow_job_artifact(
        db,
        operation_id,
        current_user,
        settings=settings,
    )
    return FileResponse(
        path,
        media_type=media_type,
        filename=filename,
        headers={
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )

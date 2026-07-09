from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.application import (
    ApplicationDraftRequest,
    ApplicationItem,
    ApplicationListResponse,
    ApplicationStatusUpdateRequest,
)
from app.schemas.auth import CurrentUser
from app.services.application_service import (
    create_application_draft,
    list_applications,
    update_application_status,
)

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=ApplicationListResponse)
def read_applications(
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicationListResponse:
    return list_applications(db, current_user, limit=limit)


@router.post("", response_model=ApplicationItem, status_code=201)
def create_application(
    request: ApplicationDraftRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicationItem:
    return create_application_draft(db, request, current_user)


@router.patch("/{application_id}/status", response_model=ApplicationItem)
def change_application_status(
    application_id: int,
    request: ApplicationStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> ApplicationItem:
    return update_application_status(db, application_id, request, current_user)

from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.core.config import Settings
from app.schemas.auth import CurrentUser
from app.schemas.privacy import AccountDeleteResponse, RetentionPurgeResponse
from app.services.privacy_service import delete_account, purge_expired_records

router = APIRouter(tags=["privacy"])


@router.post("/retention/purge", response_model=RetentionPurgeResponse)
def purge_retained_data(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> RetentionPurgeResponse:
    return purge_expired_records(db, settings, current_user)


@router.delete("/account", response_model=AccountDeleteResponse)
def delete_account_data(
    _confirmation: Annotated[
        str,
        Header(
            alias="X-Confirm-Account-Deletion",
            pattern="^delete-my-account$",
        ),
    ],
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> AccountDeleteResponse:
    return delete_account(db, settings, current_user)

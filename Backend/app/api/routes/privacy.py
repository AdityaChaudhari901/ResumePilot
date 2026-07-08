from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db, get_settings
from app.core.config import Settings
from app.schemas.auth import CurrentUser
from app.schemas.privacy import RetentionPurgeResponse
from app.services.privacy_service import purge_expired_records

router = APIRouter(prefix="/retention", tags=["retention"])


@router.post("/purge", response_model=RetentionPurgeResponse)
def purge_retained_data(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
    current_user: CurrentUser = Depends(get_current_user),
) -> RetentionPurgeResponse:
    return purge_expired_records(db, settings, current_user)

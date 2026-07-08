from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.schemas.auth import CurrentUser
from app.schemas.usage import UsageSummaryResponse
from app.services.usage_service import get_usage_summary

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("/summary", response_model=UsageSummaryResponse)
def read_usage_summary(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> UsageSummaryResponse:
    return get_usage_summary(db, current_user)

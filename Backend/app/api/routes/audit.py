from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.schemas.audit import AuditEventListResponse
from app.services.audit_service import list_audit_events

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=AuditEventListResponse)
def read_audit_events(
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    event_type: str | None = Query(default=None, min_length=1, max_length=128),
) -> AuditEventListResponse:
    return list_audit_events(db, limit=limit, event_type=event_type)

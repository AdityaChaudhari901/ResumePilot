from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import StrictBaseModel


class AuditEventResponse(StrictBaseModel):
    id: int
    event_type: str = Field(min_length=1)
    request_id: str | None = None
    payload: dict[str, Any]
    created_at: datetime


class AuditEventListResponse(StrictBaseModel):
    events: list[AuditEventResponse]
    count: int = Field(ge=0)

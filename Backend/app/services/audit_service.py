from typing import Any

from sqlalchemy.orm import Session

from app.db.models import AuditEventRecord
from app.repositories.audit_events import AuditEventRepository
from app.schemas.audit import AuditEventListResponse, AuditEventResponse


def add_audit_event(
    db: Session,
    *,
    event_type: str,
    payload: dict[str, Any],
    user_id: int | None = None,
    request_id: str | None = None,
) -> AuditEventRecord:
    record = AuditEventRecord(
        user_id=user_id,
        event_type=event_type,
        request_id=request_id,
        payload_json=_sanitize_payload(payload),
    )
    return AuditEventRepository(db).add(record)


def record_audit_event(
    db: Session,
    *,
    event_type: str,
    payload: dict[str, Any],
    user_id: int | None = None,
    request_id: str | None = None,
) -> AuditEventRecord:
    record = add_audit_event(
        db,
        event_type=event_type,
        payload=payload,
        user_id=user_id,
        request_id=request_id,
    )
    db.commit()
    db.refresh(record)
    return record


def list_audit_events(
    db: Session,
    *,
    user_id: int,
    limit: int,
    event_type: str | None = None,
) -> AuditEventListResponse:
    records = AuditEventRepository(db).list(user_id=user_id, limit=limit, event_type=event_type)
    events = [_event_response(record) for record in records]
    return AuditEventListResponse(events=events, count=len(events))


def _event_response(record: AuditEventRecord) -> AuditEventResponse:
    return AuditEventResponse(
        id=record.id,
        event_type=record.event_type,
        request_id=record.request_id,
        payload=record.payload_json,
        created_at=record.created_at,
    )


def _sanitize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted_keys = {
        "raw_text",
        "resume_text",
        "job_text",
        "email",
        "phone",
        "token",
        "api_key",
        "authorization",
    }
    sanitized: dict[str, Any] = {}
    for key, value in payload.items():
        normalized_key = key.lower()
        if (
            normalized_key in redacted_keys
            or "token" in normalized_key
            or "secret" in normalized_key
        ):
            sanitized[key] = "[redacted]"
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_payload(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize_payload(item) if isinstance(item, dict) else item for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized

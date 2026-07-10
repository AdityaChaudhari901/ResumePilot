from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_cached_settings
from app.db.models import UsageEventRecord, UserRecord
from app.repositories.usage_events import UsageEventRepository
from app.schemas.auth import CurrentUser
from app.schemas.usage import (
    PlanLimit,
    UsageEventState,
    UsageEventType,
    UsageLimitMetric,
    UsageSummaryResponse,
)

EXPORT_EVENT_TYPES = {
    UsageEventType.markdown_exported.value,
    UsageEventType.latex_exported.value,
    UsageEventType.docx_exported.value,
    UsageEventType.pdf_exported.value,
}


@dataclass(frozen=True, slots=True)
class PlanDefinition:
    name: str
    monthly_analyses: int | None
    monthly_exports: int | None
    monthly_live_ai_runs: int | None
    live_ai_enabled: bool


PLAN_DEFINITIONS: dict[str, PlanDefinition] = {
    "free": PlanDefinition(
        name="free",
        monthly_analyses=3,
        monthly_exports=5,
        monthly_live_ai_runs=0,
        live_ai_enabled=False,
    ),
    "pro": PlanDefinition(
        name="pro",
        monthly_analyses=100,
        monthly_exports=100,
        monthly_live_ai_runs=0,
        live_ai_enabled=False,
    ),
    "premium": PlanDefinition(
        name="premium",
        monthly_analyses=500,
        monthly_exports=500,
        monthly_live_ai_runs=100,
        live_ai_enabled=True,
    ),
}
DEFAULT_PLAN = PLAN_DEFINITIONS["free"]


def enforce_analysis_limit(db: Session, current_user: CurrentUser) -> None:
    _enforce_metric_limit(db, current_user, UsageLimitMetric.analyses)


def enforce_export_limit(db: Session, current_user: CurrentUser) -> None:
    _enforce_metric_limit(db, current_user, UsageLimitMetric.exports)


def enforce_live_ai_limit(db: Session, current_user: CurrentUser) -> None:
    _enforce_metric_limit(db, current_user, UsageLimitMetric.live_ai_runs)


def is_live_ai_enabled(current_user: CurrentUser) -> bool:
    return _plan_for_user(current_user).live_ai_enabled


def record_analysis_usage(
    db: Session,
    current_user: CurrentUser,
    *,
    analysis_id: int,
    report_id: int,
    workflow_mode: str,
) -> UsageEventRecord:
    metadata = {
        "analysis_id": analysis_id,
        "report_id": report_id,
        "workflow_mode": workflow_mode,
    }
    return record_usage_event(
        db,
        current_user=current_user,
        event_type=UsageEventType.analysis_created,
        metadata=metadata,
    )


def reserve_analysis_usage(
    db: Session,
    current_user: CurrentUser,
    *,
    reservation_key: str | None = None,
) -> UsageEventRecord:
    """Reserve analysis quota before remote parsing or model work begins."""
    record = add_analysis_usage_reservation(
        db,
        current_user,
        reservation_key=reservation_key,
    )
    db.commit()
    db.refresh(record)
    return record


def add_analysis_usage_reservation(
    db: Session,
    current_user: CurrentUser,
    *,
    reservation_key: str | None = None,
) -> UsageEventRecord:
    """Stage a reservation so callers can commit it atomically with durable work."""
    _lock_user_for_usage(db, current_user.id)
    enforce_analysis_limit(db, current_user)
    return add_usage_event(
        db,
        current_user=current_user,
        event_type=UsageEventType.analysis_created,
        state=UsageEventState.reserved,
        reservation_key=reservation_key,
        metadata={"status": "reserved"},
    )


def finalize_analysis_usage(
    db: Session,
    record: UsageEventRecord,
    *,
    analysis_id: int,
    report_id: int,
    workflow_mode: str,
    runtime_status: str = "completed",
) -> None:
    record.state = (
        UsageEventState.consumed.value
        if runtime_status == "completed"
        else UsageEventState.released.value
    )
    record.settled_at = datetime.now(UTC)
    record.metadata_json = {
        "status": runtime_status,
        "analysis_id": analysis_id,
        "report_id": report_id,
        "workflow_mode": workflow_mode,
    }
    db.add(record)
    db.commit()


def record_export_usage(
    db: Session,
    current_user: CurrentUser,
    *,
    report_id: int,
    export_format: str,
) -> UsageEventRecord:
    event_type = _export_event_type(export_format)
    return record_usage_event(
        db,
        current_user=current_user,
        event_type=event_type,
        metadata={"report_id": report_id, "format": export_format},
    )


def reserve_export_usage(
    db: Session,
    current_user: CurrentUser,
    *,
    report_id: int,
    export_format: str,
) -> UsageEventRecord:
    """Allocate one export inside the caller's transaction.

    The user row lock serializes quota decisions on PostgreSQL. Callers must
    commit or roll back the surrounding transaction after their audit/state
    updates are staged.
    """

    _lock_user_for_usage(db, current_user.id)
    enforce_export_limit(db, current_user)
    return add_usage_event(
        db,
        current_user=current_user,
        event_type=_export_event_type(export_format),
        state=UsageEventState.consumed,
        metadata={"report_id": report_id, "format": export_format},
    )


def add_export_usage_reservation(
    db: Session,
    current_user: CurrentUser,
    *,
    report_id: int,
    export_format: str,
    reservation_key: str,
) -> UsageEventRecord:
    """Stage an export reservation atomically with a durable export job."""
    _lock_user_for_usage(db, current_user.id)
    enforce_export_limit(db, current_user)
    return add_usage_event(
        db,
        current_user=current_user,
        event_type=_export_event_type(export_format),
        state=UsageEventState.reserved,
        reservation_key=reservation_key,
        metadata={
            "status": "reserved",
            "report_id": report_id,
            "format": export_format,
        },
    )


def finalize_export_usage(
    db: Session,
    record: UsageEventRecord,
    *,
    report_id: int,
    export_format: str,
    operation_id: str,
) -> None:
    record.state = UsageEventState.consumed.value
    record.settled_at = datetime.now(UTC)
    record.metadata_json = {
        "status": "completed",
        "report_id": report_id,
        "format": export_format,
        "operation_id": operation_id,
    }
    db.add(record)
    db.commit()


def record_live_ai_usage(
    db: Session,
    current_user: CurrentUser,
    *,
    analysis_id: int,
    cost_estimate_usd: float | None,
) -> UsageEventRecord:
    return record_usage_event(
        db,
        current_user=current_user,
        event_type=UsageEventType.live_ai_run,
        cost_estimate_usd=cost_estimate_usd,
        metadata={"analysis_id": analysis_id},
    )


def reserve_live_ai_usage(
    db: Session,
    current_user: CurrentUser,
    *,
    operation_id: str,
) -> UsageEventRecord:
    """Reserve live-provider quota before a potentially billable call."""
    _lock_user_for_usage(db, current_user.id)
    reservation_key = f"live-ai:{operation_id}"
    repository = UsageEventRepository(db)
    existing = repository.get_by_reservation_key(reservation_key)
    if existing is not None:
        return existing
    enforce_live_ai_limit(db, current_user)
    return record_usage_event(
        db,
        current_user=current_user,
        event_type=UsageEventType.live_ai_run,
        state=UsageEventState.reserved,
        reservation_key=reservation_key,
        metadata={"status": "reserved"},
    )


def finalize_live_ai_usage(
    db: Session,
    record: UsageEventRecord,
    *,
    analysis_id: int,
    runtime_status: str,
    cost_estimate_usd: float | None,
) -> None:
    record.state = (
        UsageEventState.consumed.value
        if runtime_status == "completed"
        else UsageEventState.released.value
    )
    record.settled_at = datetime.now(UTC)
    record.metadata_json = {"status": runtime_status, "analysis_id": analysis_id}
    record.cost_estimate_usd = cost_estimate_usd
    db.add(record)
    db.commit()


def scrub_live_ai_usage_for_privacy(
    db: Session,
    *,
    user_id: int,
    operation_id: str,
    analysis_id: int | None = None,
) -> None:
    """Remove operation/report correlation while preserving aggregate accounting."""

    reservation_key = f"live-ai:{operation_id}"
    candidates = list(
        db.scalars(
            select(UsageEventRecord).where(
                UsageEventRecord.user_id == user_id,
                UsageEventRecord.event_type.in_(
                    {
                        UsageEventType.live_ai_run.value,
                        UsageEventType.crewai_run.value,
                    }
                ),
            )
        )
    )
    for record in candidates:
        metadata_analysis_id = (record.metadata_json or {}).get("analysis_id")
        if record.reservation_key != reservation_key and (
            analysis_id is None or metadata_analysis_id != analysis_id
        ):
            continue
        previous_state = record.state
        if record.state == UsageEventState.reserved.value:
            record.state = UsageEventState.released.value
            record.settled_at = datetime.now(UTC)
        record.reservation_key = None
        record.metadata_json = {
            "status": "privacy_deleted",
            "previous_state": previous_state,
        }
        db.add(record)


def record_usage_event(
    db: Session,
    *,
    current_user: CurrentUser,
    event_type: UsageEventType,
    quantity: int = 1,
    cost_estimate_usd: float | None = None,
    metadata: dict[str, Any] | None = None,
    state: UsageEventState = UsageEventState.consumed,
    reservation_key: str | None = None,
) -> UsageEventRecord:
    record = add_usage_event(
        db,
        current_user=current_user,
        event_type=event_type,
        quantity=quantity,
        cost_estimate_usd=cost_estimate_usd,
        metadata=metadata,
        state=state,
        reservation_key=reservation_key,
    )
    db.commit()
    db.refresh(record)
    return record


def add_usage_event(
    db: Session,
    *,
    current_user: CurrentUser,
    event_type: UsageEventType,
    quantity: int = 1,
    cost_estimate_usd: float | None = None,
    metadata: dict[str, Any] | None = None,
    state: UsageEventState = UsageEventState.consumed,
    reservation_key: str | None = None,
) -> UsageEventRecord:
    now = datetime.now(UTC)
    record = UsageEventRecord(
        user_id=current_user.id,
        event_type=event_type.value,
        quantity=quantity,
        cost_estimate_usd=cost_estimate_usd,
        metadata_json=metadata or {},
        state=state.value,
        reservation_key=reservation_key,
        reserved_at=now if state == UsageEventState.reserved else None,
        settled_at=now if state != UsageEventState.reserved else None,
    )
    repository = UsageEventRepository(db)
    repository.add(record)
    return record


def get_usage_summary(db: Session, current_user: CurrentUser) -> UsageSummaryResponse:
    period_start, period_end = _current_period()
    plan = _plan_for_user(current_user)
    repository = UsageEventRepository(db)
    analysis_count = repository.quantity_sum(
        user_id=current_user.id,
        event_types={UsageEventType.analysis_created.value},
        start_at=period_start,
        end_at=period_end,
        states={UsageEventState.consumed.value},
    )
    export_count = repository.quantity_sum(
        user_id=current_user.id,
        event_types=EXPORT_EVENT_TYPES,
        start_at=period_start,
        end_at=period_end,
        states={UsageEventState.consumed.value},
    )
    live_ai_count = repository.quantity_sum(
        user_id=current_user.id,
        event_types={UsageEventType.live_ai_run.value, UsageEventType.crewai_run.value},
        start_at=period_start,
        end_at=period_end,
        states={UsageEventState.consumed.value},
    )

    return UsageSummaryResponse(
        user_id=current_user.id,
        plan=plan.name,
        subscription_status=current_user.subscription_status,
        current_period_start=period_start,
        current_period_end=period_end,
        limits=[
            _plan_limit(
                metric=UsageLimitMetric.analyses,
                used=analysis_count,
                limit=plan.monthly_analyses,
                reset_at=period_end,
            ),
            _plan_limit(
                metric=UsageLimitMetric.exports,
                used=export_count,
                limit=plan.monthly_exports,
                reset_at=period_end,
            ),
            _plan_limit(
                metric=UsageLimitMetric.live_ai_runs,
                used=live_ai_count,
                limit=plan.monthly_live_ai_runs,
                reset_at=period_end,
            ),
        ],
        total_cost_estimate_usd=round(
            repository.cost_sum(
                user_id=current_user.id,
                start_at=period_start,
                end_at=period_end,
            ),
            6,
        ),
        live_ai_enabled=plan.live_ai_enabled,
    )


def _enforce_metric_limit(
    db: Session,
    current_user: CurrentUser,
    metric: UsageLimitMetric,
) -> None:
    period_start, period_end = _current_period()
    plan = _plan_for_user(current_user)
    event_types, maximum = _metric_limit_definition(metric, plan)
    if maximum is None:
        return
    reserved_after = datetime.now(UTC) - timedelta(
        seconds=get_cached_settings().usage_reservation_ttl_seconds
    )
    used_or_reserved = UsageEventRepository(db).quantity_sum(
        user_id=current_user.id,
        event_types=event_types,
        start_at=period_start,
        end_at=period_end,
        states={UsageEventState.consumed.value, UsageEventState.reserved.value},
        reserved_after=reserved_after,
    )
    if used_or_reserved < maximum:
        return
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": "plan_limit_reached",
            "metric": metric.value,
            "plan": plan.name,
            "used": used_or_reserved,
            "limit": maximum,
            "reset_at": period_end.isoformat(),
            "message": (
                f"{plan.name} plan {metric.value} limit reached. "
                "Upgrade or wait for the next billing period."
            ),
        },
    )


def release_usage_reservation(
    db: Session,
    record: UsageEventRecord,
    *,
    runtime_status: str,
    metadata: dict[str, Any] | None = None,
) -> None:
    if record.state != UsageEventState.reserved.value:
        return
    record.state = UsageEventState.released.value
    record.settled_at = datetime.now(UTC)
    record.metadata_json = {"status": runtime_status, **(metadata or {})}
    db.add(record)
    db.commit()


def _metric_limit_definition(
    metric: UsageLimitMetric,
    plan: PlanDefinition,
) -> tuple[set[str], int | None]:
    if metric == UsageLimitMetric.analyses:
        return {UsageEventType.analysis_created.value}, plan.monthly_analyses
    if metric == UsageLimitMetric.exports:
        return EXPORT_EVENT_TYPES, plan.monthly_exports
    return {
        UsageEventType.live_ai_run.value,
        UsageEventType.crewai_run.value,
    }, plan.monthly_live_ai_runs


def _export_event_type(export_format: str) -> UsageEventType:
    event_type_by_format = {
        "markdown": UsageEventType.markdown_exported,
        "latex": UsageEventType.latex_exported,
        "docx": UsageEventType.docx_exported,
        "pdf": UsageEventType.pdf_exported,
    }
    return event_type_by_format[export_format]


def _lock_user_for_usage(db: Session, user_id: int) -> None:
    user = db.scalar(select(UserRecord).where(UserRecord.id == user_id).with_for_update())
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")


def _plan_for_user(current_user: CurrentUser) -> PlanDefinition:
    return PLAN_DEFINITIONS.get(current_user.plan.lower(), DEFAULT_PLAN)


def _current_period() -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start, end


def _plan_limit(
    *,
    metric: UsageLimitMetric,
    used: int,
    limit: int | None,
    reset_at: datetime,
) -> PlanLimit:
    remaining = None if limit is None else max(limit - used, 0)
    return PlanLimit(metric=metric, used=used, limit=limit, remaining=remaining, reset_at=reset_at)

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.db.models import UsageEventRecord
from app.repositories.usage_events import UsageEventRepository
from app.schemas.auth import CurrentUser
from app.schemas.usage import (
    PlanLimit,
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
    monthly_crewai_runs: int | None
    live_crewai_enabled: bool


PLAN_DEFINITIONS: dict[str, PlanDefinition] = {
    "free": PlanDefinition(
        name="free",
        monthly_analyses=3,
        monthly_exports=5,
        monthly_crewai_runs=0,
        live_crewai_enabled=False,
    ),
    "pro": PlanDefinition(
        name="pro",
        monthly_analyses=100,
        monthly_exports=100,
        monthly_crewai_runs=0,
        live_crewai_enabled=False,
    ),
    "premium": PlanDefinition(
        name="premium",
        monthly_analyses=500,
        monthly_exports=500,
        monthly_crewai_runs=100,
        live_crewai_enabled=True,
    ),
}
DEFAULT_PLAN = PLAN_DEFINITIONS["free"]


def enforce_analysis_limit(db: Session, current_user: CurrentUser) -> None:
    _enforce_metric_limit(db, current_user, UsageLimitMetric.analyses)


def enforce_export_limit(db: Session, current_user: CurrentUser) -> None:
    _enforce_metric_limit(db, current_user, UsageLimitMetric.exports)


def enforce_crewai_limit(db: Session, current_user: CurrentUser) -> None:
    _enforce_metric_limit(db, current_user, UsageLimitMetric.crewai_runs)


def is_live_crewai_enabled(current_user: CurrentUser) -> bool:
    return _plan_for_user(current_user).live_crewai_enabled


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


def record_export_usage(
    db: Session,
    current_user: CurrentUser,
    *,
    report_id: int,
    export_format: str,
) -> UsageEventRecord:
    event_type_by_format = {
        "markdown": UsageEventType.markdown_exported,
        "latex": UsageEventType.latex_exported,
        "docx": UsageEventType.docx_exported,
        "pdf": UsageEventType.pdf_exported,
    }
    event_type = event_type_by_format[export_format]
    return record_usage_event(
        db,
        current_user=current_user,
        event_type=event_type,
        metadata={"report_id": report_id, "format": export_format},
    )


def record_crewai_usage(
    db: Session,
    current_user: CurrentUser,
    *,
    analysis_id: int,
    cost_estimate_usd: float | None,
) -> UsageEventRecord:
    return record_usage_event(
        db,
        current_user=current_user,
        event_type=UsageEventType.crewai_run,
        cost_estimate_usd=cost_estimate_usd,
        metadata={"analysis_id": analysis_id},
    )


def record_usage_event(
    db: Session,
    *,
    current_user: CurrentUser,
    event_type: UsageEventType,
    quantity: int = 1,
    cost_estimate_usd: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> UsageEventRecord:
    record = UsageEventRecord(
        user_id=current_user.id,
        event_type=event_type.value,
        quantity=quantity,
        cost_estimate_usd=cost_estimate_usd,
        metadata_json=metadata or {},
    )
    repository = UsageEventRepository(db)
    repository.add(record)
    db.commit()
    db.refresh(record)
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
    )
    export_count = repository.quantity_sum(
        user_id=current_user.id,
        event_types=EXPORT_EVENT_TYPES,
        start_at=period_start,
        end_at=period_end,
    )
    crewai_count = repository.quantity_sum(
        user_id=current_user.id,
        event_types={UsageEventType.crewai_run.value},
        start_at=period_start,
        end_at=period_end,
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
                metric=UsageLimitMetric.crewai_runs,
                used=crewai_count,
                limit=plan.monthly_crewai_runs,
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
        live_crewai_enabled=plan.live_crewai_enabled,
    )


def _enforce_metric_limit(
    db: Session,
    current_user: CurrentUser,
    metric: UsageLimitMetric,
) -> None:
    summary = get_usage_summary(db, current_user)
    limit = next(item for item in summary.limits if item.metric == metric)
    if limit.limit is None or limit.used < limit.limit:
        return
    raise HTTPException(
        status_code=status.HTTP_402_PAYMENT_REQUIRED,
        detail={
            "code": "plan_limit_reached",
            "metric": metric.value,
            "plan": summary.plan,
            "used": limit.used,
            "limit": limit.limit,
            "reset_at": limit.reset_at.isoformat(),
            "message": (
                f"{summary.plan} plan {metric.value} limit reached. "
                "Upgrade or wait for the next billing period."
            ),
        },
    )


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

from datetime import datetime
from enum import StrEnum

from pydantic import Field

from app.schemas.common import StrictBaseModel


class UsageEventType(StrEnum):
    analysis_created = "analysis_created"
    markdown_exported = "markdown_exported"
    latex_exported = "latex_exported"
    docx_exported = "docx_exported"
    pdf_exported = "pdf_exported"
    live_ai_run = "live_ai_run"
    # Historical usage rows may still contain this value.
    crewai_run = "crewai_run"


class UsageEventState(StrEnum):
    reserved = "reserved"
    consumed = "consumed"
    released = "released"


class UsageLimitMetric(StrEnum):
    analyses = "analyses"
    exports = "exports"
    live_ai_runs = "live_ai_runs"


class PlanLimit(StrictBaseModel):
    metric: UsageLimitMetric
    used: int = Field(ge=0)
    limit: int | None = Field(default=None, ge=0)
    remaining: int | None = Field(default=None, ge=0)
    reset_at: datetime


class UsageSummaryResponse(StrictBaseModel):
    user_id: int
    plan: str
    subscription_status: str
    current_period_start: datetime
    current_period_end: datetime
    limits: list[PlanLimit]
    total_cost_estimate_usd: float = Field(ge=0)
    live_ai_enabled: bool

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
    crewai_run = "crewai_run"


class UsageLimitMetric(StrEnum):
    analyses = "analyses"
    exports = "exports"
    crewai_runs = "crewai_runs"


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
    live_crewai_enabled: bool

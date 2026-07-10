from enum import StrEnum
from typing import Any

from pydantic import Field, model_validator

from app.schemas.common import Confidence, StrictBaseModel, ValidationSeverity
from app.schemas.report import (
    ApplicationReport,
    AtsKeywordSuggestion,
    InterviewQuestionGroup,
    TailoredBullet,
)


class AgentWorkflowMode(StrEnum):
    deterministic_fallback = "deterministic_fallback"
    langgraph = "langgraph"
    # Historical reports may still contain this value. It is not an active runtime mode.
    crewai = "crewai"


class AgentStepName(StrEnum):
    jd_parser = "jd_parser"
    langgraph_runtime = "langgraph_runtime"
    human_approval = "human_approval"
    # Historical traces may still contain this value.
    crewai_runtime = "crewai_runtime"
    resume_match = "resume_match"
    ats_optimizer = "ats_optimizer"
    cover_letter = "cover_letter"
    interview_coach = "interview_coach"
    validation_gate = "validation_gate"


class AgentStepTrace(StrictBaseModel):
    name: AgentStepName
    status: str = Field(pattern="^(completed|degraded|failed)$")
    summary: str = Field(min_length=1)
    duration_ms: int | None = Field(default=None, ge=0)


class AgentTokenUsage(StrictBaseModel):
    total_tokens: int = Field(default=0, ge=0)
    prompt_tokens: int = Field(default=0, ge=0)
    completion_tokens: int = Field(default=0, ge=0)
    cached_prompt_tokens: int = Field(default=0, ge=0)
    reasoning_tokens: int = Field(default=0, ge=0)
    cache_creation_tokens: int = Field(default=0, ge=0)
    successful_requests: int = Field(default=0, ge=0)


class ResumeMatchAgentOutput(StrictBaseModel):
    summary: str = Field(min_length=1)
    strongest_matches: list[str] = Field(default_factory=list)
    weak_areas: list[str] = Field(default_factory=list)
    recommended_positioning: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: Confidence


class AtsOptimizerAgentOutput(StrictBaseModel):
    tailored_bullets: list[TailoredBullet] = Field(default_factory=list)
    keyword_suggestions: list[AtsKeywordSuggestion] = Field(default_factory=list)
    section_recommendations: list[str] = Field(default_factory=list)


class CoverLetterAgentOutput(StrictBaseModel):
    draft: str = Field(min_length=1)
    confidence_note: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)


class InterviewCoachAgentOutput(StrictBaseModel):
    question_groups: list[InterviewQuestionGroup] = Field(min_length=1)


class LiveDraftSections(StrictBaseModel):
    resume_match: ResumeMatchAgentOutput
    cover_letter: CoverLetterAgentOutput
    interview_coach: InterviewCoachAgentOutput
    step_durations_ms: dict[str, int] = Field(default_factory=dict)
    token_usage: AgentTokenUsage | None = None


class AgentWorkflowTrace(StrictBaseModel):
    mode: AgentWorkflowMode
    steps: list[AgentStepTrace] = Field(min_length=1)
    validation_warning_codes: list[str] = Field(default_factory=list)
    validation_status: ValidationSeverity = ValidationSeverity.pass_
    duration_ms: int | None = Field(default=None, ge=0)
    provider: str | None = Field(default=None, min_length=1)
    model: str | None = Field(default=None, min_length=1)
    token_usage: AgentTokenUsage | None = None
    cost_estimate_usd: float | None = Field(default=None, ge=0)
    runtime_metadata: dict[str, str | int | float | bool | None] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def infer_legacy_validation_status(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "validation_status" in value:
            return value
        payload = dict(value)
        payload["validation_status"] = (
            ValidationSeverity.warn
            if payload.get("validation_warning_codes")
            else ValidationSeverity.pass_
        )
        return payload


class AgentWorkflowResult(StrictBaseModel):
    report: ApplicationReport
    trace: AgentWorkflowTrace


class ReportWorkflowTraceResponse(StrictBaseModel):
    analysis_id: int
    report_id: int
    trace: AgentWorkflowTrace

from enum import StrEnum

from pydantic import Field

from app.schemas.common import Confidence, StrictBaseModel
from app.schemas.report import (
    ApplicationReport,
    AtsKeywordSuggestion,
    InterviewQuestionGroup,
    TailoredBullet,
)


class AgentWorkflowMode(StrEnum):
    deterministic_fallback = "deterministic_fallback"
    crewai = "crewai"


class AgentStepName(StrEnum):
    jd_parser = "jd_parser"
    resume_match = "resume_match"
    ats_optimizer = "ats_optimizer"
    cover_letter = "cover_letter"
    interview_coach = "interview_coach"
    validation_gate = "validation_gate"


class AgentStepTrace(StrictBaseModel):
    name: AgentStepName
    status: str = Field(pattern="^(completed|degraded|failed)$")
    summary: str = Field(min_length=1)


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


class AgentWorkflowTrace(StrictBaseModel):
    mode: AgentWorkflowMode
    steps: list[AgentStepTrace] = Field(min_length=1)
    validation_warning_codes: list[str] = Field(default_factory=list)


class AgentWorkflowResult(StrictBaseModel):
    report: ApplicationReport
    trace: AgentWorkflowTrace

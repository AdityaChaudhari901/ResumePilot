from datetime import datetime
from typing import Any

from pydantic import Field, model_validator

from app.schemas.common import (
    StrictBaseModel,
    ValidationSeverity,
    ValidationWarning,
    validation_status_from_warnings,
)
from app.schemas.match import MatchedSkill, MissingSkill, WeakSkill


class TailoredBullet(StrictBaseModel):
    bullet: str = Field(min_length=1)
    evidence_ids: list[str] = Field(min_length=1)
    jd_keywords_used: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)


class AtsKeywordSuggestion(StrictBaseModel):
    keyword: str = Field(min_length=1)
    status: str = Field(pattern="^(supported|add_only_if_true|missing)$")
    evidence_ids: list[str] = Field(default_factory=list)
    note: str = Field(min_length=1)


class InterviewQuestionGroup(StrictBaseModel):
    category: str = Field(min_length=1)
    questions: list[str] = Field(min_length=1)
    suggested_answer_evidence_ids: list[str] = Field(default_factory=list)


class ApplicationReport(StrictBaseModel):
    analysis_id: int
    resume_id: int
    job_id: int
    executive_summary: str = Field(min_length=1)
    match_score: float = Field(ge=0, le=100)
    matched_skills: list[MatchedSkill] = Field(default_factory=list)
    missing_skills: list[MissingSkill] = Field(default_factory=list)
    weak_skills: list[WeakSkill] = Field(default_factory=list)
    tailored_bullets: list[TailoredBullet] = Field(default_factory=list)
    ats_keywords: list[AtsKeywordSuggestion] = Field(default_factory=list)
    cover_letter: str = Field(min_length=1)
    cover_letter_evidence_ids: list[str] = Field(default_factory=list)
    interview_questions: list[InterviewQuestionGroup] = Field(default_factory=list)
    validation_warnings: list[ValidationWarning] = Field(default_factory=list)
    validation_status: ValidationSeverity = ValidationSeverity.pass_
    next_actions: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def infer_legacy_validation_status(cls, value: Any) -> Any:
        if not isinstance(value, dict) or "validation_status" in value:
            return value
        payload = dict(value)
        warnings = [
            ValidationWarning.model_validate(warning)
            for warning in payload.get("validation_warnings") or []
        ]
        payload["validation_status"] = validation_status_from_warnings(warnings)
        return payload


class ReportHistoryItem(StrictBaseModel):
    report_id: int
    analysis_id: int
    resume_id: int
    job_id: int
    company: str | None = None
    role: str | None = None
    resume_candidate_name: str | None = None
    status: str
    match_score: float = Field(ge=0, le=100)
    workflow_mode: str
    validation_warnings_count: int = Field(ge=0)
    matched_skills_count: int = Field(ge=0)
    missing_skills_count: int = Field(ge=0)
    weak_skills_count: int = Field(ge=0)
    created_at: datetime


class ReportHistoryResponse(StrictBaseModel):
    items: list[ReportHistoryItem] = Field(default_factory=list)

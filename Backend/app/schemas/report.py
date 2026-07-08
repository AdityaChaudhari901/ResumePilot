from pydantic import Field

from app.schemas.common import StrictBaseModel, ValidationWarning
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
    interview_questions: list[InterviewQuestionGroup] = Field(default_factory=list)
    validation_warnings: list[ValidationWarning] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)

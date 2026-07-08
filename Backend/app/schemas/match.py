from enum import StrEnum

from pydantic import Field

from app.schemas.common import Confidence, StrictBaseModel


class MatchType(StrEnum):
    exact = "exact"
    synonym = "synonym"
    inferred = "inferred"


class MatchedSkill(StrictBaseModel):
    skill: str = Field(min_length=1)
    match_type: MatchType
    resume_evidence_ids: list[str] = Field(min_length=1)
    job_evidence_text: str = Field(min_length=1)
    confidence: Confidence


class MissingSkill(StrictBaseModel):
    skill: str = Field(min_length=1)
    importance: str = Field(pattern="^(required|preferred)$")
    job_evidence_text: str = Field(min_length=1)
    why_it_matters: str = Field(min_length=1)
    recommendation: str = Field(min_length=1)


class WeakSkill(StrictBaseModel):
    skill: str = Field(min_length=1)
    resume_evidence_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)


class MatchResult(StrictBaseModel):
    score: float = Field(ge=0, le=100)
    required_skill_score: float = Field(ge=0, le=100)
    preferred_skill_score: float = Field(ge=0, le=100)
    responsibility_alignment_score: float = Field(ge=0, le=100)
    experience_level_score: float = Field(ge=0, le=100)
    domain_keyword_score: float = Field(ge=0, le=100)
    resume_quality_score: float = Field(ge=0, le=100)
    matched_skills: list[MatchedSkill] = Field(default_factory=list)
    missing_skills: list[MissingSkill] = Field(default_factory=list)
    weak_skills: list[WeakSkill] = Field(default_factory=list)
    confidence: Confidence

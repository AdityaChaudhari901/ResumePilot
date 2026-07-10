from enum import StrEnum

from pydantic import Field, HttpUrl, model_validator

from app.schemas.common import Confidence, StrictBaseModel, ValidationWarning


class JobSkill(StrictBaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    importance: str = Field(pattern="^(required|preferred|keyword)$")
    evidence_text: str = Field(min_length=1)
    confidence: Confidence = Confidence.medium


class JobProfile(StrictBaseModel):
    job_id: int
    company: str | None = None
    role_title: str | None = None
    location: str | None = None
    employment_type: str | None = None
    required_skills: list[JobSkill] = Field(default_factory=list)
    preferred_skills: list[JobSkill] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    experience_level: str | None = None
    keywords: list[str] = Field(default_factory=list)
    benefits: list[str] = Field(default_factory=list)
    unclear_items: list[str] = Field(default_factory=list)
    warnings: list[ValidationWarning] = Field(default_factory=list)


class JobPreviewStatus(StrEnum):
    ready = "ready"
    needs_review = "needs_review"
    blocked_private = "blocked_private"
    too_short = "too_short"
    missing_requirements = "missing_requirements"


class JobPreviewQualityCheck(StrictBaseModel):
    code: str = Field(min_length=1)
    status: str = Field(pattern="^(pass|warn|fail)$")
    message: str = Field(min_length=1)


class JobAnalysisRequest(StrictBaseModel):
    resume_id: int
    application_id: int | None = None
    job_url: HttpUrl | None = None
    job_text: str | None = Field(default=None, min_length=40)
    company: str | None = None
    role: str | None = None
    reviewed_job_profile: JobProfile | None = None
    allow_live_ai_processing: bool = False

    @model_validator(mode="after")
    def require_job_input(self) -> "JobAnalysisRequest":
        if self.job_url is None and not self.job_text and self.reviewed_job_profile is None:
            raise ValueError("Either job_url, job_text, or reviewed_job_profile is required")
        return self


class JobAnalysisResponse(StrictBaseModel):
    analysis_id: int
    report_id: int
    match_score: float = Field(ge=0, le=100)
    status: str


class JobPreviewRequest(StrictBaseModel):
    job_url: HttpUrl


class JobPreviewResponse(StrictBaseModel):
    job_url: HttpUrl
    profile: JobProfile
    raw_text_char_count: int = Field(ge=0)
    status: JobPreviewStatus
    parser: str = Field(min_length=1)
    quality_checks: list[JobPreviewQualityCheck] = Field(default_factory=list)

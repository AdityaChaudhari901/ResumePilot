from enum import StrEnum

from pydantic import Field, HttpUrl, model_validator

from app.schemas.common import Confidence, StrictBaseModel, ValidationWarning
from app.schemas.match import MatchScoreStatus, ScoringVersion

MIN_JOB_TEXT_CHARS = 40
MAX_JOB_TEXT_CHARS = 50_000


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


class JobSourceType(StrEnum):
    url = "url"
    pasted_text = "pasted_text"


class JobPreviewQualityCheck(StrictBaseModel):
    code: str = Field(min_length=1)
    status: str = Field(pattern="^(pass|warn|fail)$")
    message: str = Field(min_length=1)


class JobAnalysisRequest(StrictBaseModel):
    resume_id: int
    application_id: int | None = None
    job_url: HttpUrl | None = None
    job_text: str | None = Field(
        default=None,
        min_length=MIN_JOB_TEXT_CHARS,
        max_length=MAX_JOB_TEXT_CHARS,
    )
    company: str | None = None
    role: str | None = None
    reviewed_job_profile: JobProfile | None = None
    allow_live_ai_processing: bool = False

    @model_validator(mode="after")
    def require_job_input(self) -> "JobAnalysisRequest":
        source_count = int(self.job_url is not None) + int(bool(self.job_text))
        if self.application_id is not None:
            if source_count or self.reviewed_job_profile is not None:
                raise ValueError(
                    "application_id cannot be combined with job_url, job_text, or "
                    "reviewed_job_profile"
                )
            return self
        if source_count != 1:
            raise ValueError("Provide exactly one of job_url or job_text")
        return self


class JobAnalysisResponse(StrictBaseModel):
    analysis_id: int
    report_id: int
    match_score: float = Field(ge=0, le=100)
    scoring_version: ScoringVersion = ScoringVersion.legacy_unversioned
    score_status: MatchScoreStatus = MatchScoreStatus.scored
    status: str


class JobPreviewRequest(StrictBaseModel):
    job_url: HttpUrl | None = None
    job_text: str | None = Field(
        default=None,
        min_length=MIN_JOB_TEXT_CHARS,
        max_length=MAX_JOB_TEXT_CHARS,
    )

    @model_validator(mode="after")
    def require_one_source(self) -> "JobPreviewRequest":
        if int(self.job_url is not None) + int(bool(self.job_text)) != 1:
            raise ValueError("Provide exactly one of job_url or job_text")
        return self


class JobPreviewResponse(StrictBaseModel):
    source_type: JobSourceType
    job_url: HttpUrl | None = None
    reviewed_job_text: str | None = Field(default=None, max_length=MAX_JOB_TEXT_CHARS)
    source_content_hash: str | None = Field(default=None, pattern="^[a-f0-9]{64}$")
    profile: JobProfile
    raw_text_char_count: int = Field(ge=0)
    status: JobPreviewStatus
    parser: str = Field(min_length=1)
    quality_checks: list[JobPreviewQualityCheck] = Field(default_factory=list)

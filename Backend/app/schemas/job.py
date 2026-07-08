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


class JobAnalysisRequest(StrictBaseModel):
    resume_id: int
    job_url: HttpUrl | None = None
    job_text: str | None = Field(default=None, min_length=40)
    company: str | None = None
    role: str | None = None

    @model_validator(mode="after")
    def require_job_input(self) -> "JobAnalysisRequest":
        if self.job_url is None and not self.job_text:
            raise ValueError("Either job_url or job_text is required")
        return self


class JobAnalysisResponse(StrictBaseModel):
    analysis_id: int
    report_id: int
    match_score: float = Field(ge=0, le=100)
    status: str

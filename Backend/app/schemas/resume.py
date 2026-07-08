from pydantic import EmailStr, Field, HttpUrl

from app.schemas.common import Confidence, SkillCategory, StrictBaseModel, ValidationWarning


class CandidateProfile(StrictBaseModel):
    name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    location: str | None = None
    links: list[HttpUrl] = Field(default_factory=list)


class ResumeFact(StrictBaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    section: str = Field(min_length=1)
    confidence: Confidence = Confidence.medium


class ResumeSkill(StrictBaseModel):
    name: str = Field(min_length=1)
    category: SkillCategory = SkillCategory.other
    evidence_ids: list[str] = Field(min_length=1)
    confidence: Confidence = Confidence.medium


class ResumeProfile(StrictBaseModel):
    resume_id: int
    candidate: CandidateProfile
    skills: list[ResumeSkill] = Field(default_factory=list)
    experience: list[ResumeFact] = Field(default_factory=list)
    projects: list[ResumeFact] = Field(default_factory=list)
    education: list[ResumeFact] = Field(default_factory=list)
    certifications: list[ResumeFact] = Field(default_factory=list)
    facts: list[ResumeFact] = Field(default_factory=list)
    warnings: list[ValidationWarning] = Field(default_factory=list)


class ResumeUploadResponse(StrictBaseModel):
    resume_id: int
    candidate_name: str | None = None
    status: str
    warnings: list[ValidationWarning] = Field(default_factory=list)

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_assignment=True)


class Confidence(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class SkillCategory(StrEnum):
    programming_language = "programming_language"
    backend_framework = "backend_framework"
    frontend_framework = "frontend_framework"
    database = "database"
    cloud_devops = "cloud_devops"
    ai_ml = "ai_ml"
    data_tool = "data_tool"
    testing = "testing"
    security = "security"
    soft_skill = "soft_skill"
    domain = "domain"
    other = "other"


class ValidationWarning(StrictBaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    evidence_ids: list[str] = Field(default_factory=list)

from datetime import datetime
from enum import StrEnum

from pydantic import Field, model_validator

from app.schemas.common import StrictBaseModel, ValidationWarning


class TailoredResumeDraftStatus(StrEnum):
    draft = "draft"
    reviewed = "reviewed"
    exported = "exported"


class TailoredResumeItemStatus(StrEnum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class TailoredResumeItem(StrictBaseModel):
    id: str = Field(min_length=1)
    source_bullet: str = Field(min_length=1)
    suggested_bullet: str = Field(min_length=1)
    edited_bullet: str | None = Field(default=None, min_length=1, max_length=1200)
    evidence_ids: list[str] = Field(min_length=1)
    evidence_labels: list[str] = Field(default_factory=list)
    evidence_texts: list[str] = Field(default_factory=list)
    jd_keywords_used: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    status: TailoredResumeItemStatus = TailoredResumeItemStatus.pending
    validation_warnings: list[ValidationWarning] = Field(default_factory=list)


class TailoredResumeItemUpdateRequest(StrictBaseModel):
    status: TailoredResumeItemStatus | None = None
    edited_bullet: str | None = Field(default=None, min_length=1, max_length=1200)
    reset_edited_bullet: bool = False

    @model_validator(mode="after")
    def reject_conflicting_edit_requests(self) -> "TailoredResumeItemUpdateRequest":
        if self.reset_edited_bullet and self.edited_bullet is not None:
            raise ValueError("edited_bullet cannot be provided when reset_edited_bullet is true")
        return self


class TailoredResumeDraftResponse(StrictBaseModel):
    id: int
    application_id: int
    report_id: int
    status: TailoredResumeDraftStatus
    items: list[TailoredResumeItem]
    accepted_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    pending_count: int = Field(ge=0)
    export_ready: bool
    created_at: datetime
    updated_at: datetime

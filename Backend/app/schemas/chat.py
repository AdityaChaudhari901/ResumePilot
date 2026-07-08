from pydantic import Field

from app.schemas.common import StrictBaseModel


class OpenClawCommandRequest(StrictBaseModel):
    command: str = Field(min_length=1)
    args: str = Field(min_length=1)
    sender: str = Field(min_length=1)
    session_id: str = Field(min_length=1)


class OpenClawCommandResponse(StrictBaseModel):
    status: str
    message: str
    analysis_id: int | None = None
    report_id: int | None = None
    markdown: str | None = None

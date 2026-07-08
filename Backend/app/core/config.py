from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "ResumePilot"
    app_env: str = Field(default="development", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")

    database_url: str = Field(
        default_factory=lambda: f"sqlite:///{Path.home() / '.resumepilot' / 'resumepilot.db'}",
        alias="DATABASE_URL",
    )
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".resumepilot", alias="RESUMEPILOT_DATA_DIR"
    )
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    jobcopilot_api_token: str | None = Field(default=None, alias="JOBCOPILOT_API_TOKEN")
    openclaw_sender_allowlist: list[str] = Field(
        default_factory=list, alias="OPENCLAW_SENDER_ALLOWLIST"
    )

    allowed_resume_extensions: frozenset[str] = frozenset(
        {".pdf", ".docx", ".txt", ".md", ".markdown"}
    )

    @field_validator("openclaw_sender_allowlist", mode="before")
    @classmethod
    def parse_sender_allowlist(cls, value: object) -> list[str]:
        if value is None or value == "":
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("OPENCLAW_SENDER_ALLOWLIST must be a comma-separated string or list")

    @field_validator("data_dir")
    @classmethod
    def expand_data_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @property
    def debug(self) -> bool:
        return self.app_debug

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"


@lru_cache
def get_cached_settings() -> Settings:
    return Settings()

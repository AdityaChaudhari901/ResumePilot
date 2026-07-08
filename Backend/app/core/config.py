from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.schemas.agent import AgentWorkflowMode


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
    openclaw_sender_allowlist_raw: str = Field(default="", alias="OPENCLAW_SENDER_ALLOWLIST")
    llm_provider: str = Field(default="vertex", alias="LLM_PROVIDER")
    vertex_project_id: str | None = Field(default=None, alias="VERTEX_PROJECT_ID")
    vertex_region: str = Field(default="global", alias="VERTEX_REGION")
    llm_model: str = Field(default="gemini-3.5-flash", alias="LLM_MODEL")
    agent_workflow_mode: AgentWorkflowMode = Field(
        default=AgentWorkflowMode.deterministic_fallback,
        alias="AGENT_WORKFLOW_MODE",
    )
    crewai_llm_model: str | None = Field(default=None, alias="CREWAI_LLM_MODEL")
    crewai_max_iter: int = Field(default=2, ge=1, le=10, alias="CREWAI_MAX_ITER")
    crewai_timeout_seconds: int = Field(default=60, ge=10, le=300, alias="CREWAI_TIMEOUT_SECONDS")
    crewai_temperature: float = Field(default=0.2, ge=0, le=1, alias="CREWAI_TEMPERATURE")
    latex_compile_timeout_seconds: int = Field(
        default=20,
        ge=5,
        le=120,
        alias="LATEX_COMPILE_TIMEOUT_SECONDS",
    )
    latex_pdf_max_bytes: int = Field(
        default=5 * 1024 * 1024,
        ge=1024,
        le=50 * 1024 * 1024,
        alias="LATEX_PDF_MAX_BYTES",
    )

    allowed_resume_extensions: frozenset[str] = frozenset(
        {".pdf", ".docx", ".txt", ".md", ".markdown"}
    )

    @field_validator("data_dir")
    @classmethod
    def expand_data_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("llm_provider", "vertex_region", "llm_model")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @field_validator("vertex_project_id", "crewai_llm_model")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @property
    def debug(self) -> bool:
        return self.app_debug

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def openclaw_sender_allowlist(self) -> list[str]:
        return [
            item.strip() for item in self.openclaw_sender_allowlist_raw.split(",") if item.strip()
        ]


@lru_cache
def get_cached_settings() -> Settings:
    return Settings()

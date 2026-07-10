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
    auto_create_db_schema: bool | None = Field(default=None, alias="AUTO_CREATE_DB_SCHEMA")
    require_db_migrations: bool | None = Field(default=None, alias="REQUIRE_DB_MIGRATIONS")

    database_url: str = Field(
        default_factory=lambda: f"sqlite:///{Path.home() / '.resumepilot' / 'resumepilot.db'}",
        alias="DATABASE_URL",
    )
    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".resumepilot", alias="RESUMEPILOT_DATA_DIR"
    )
    max_upload_bytes: int = Field(default=5 * 1024 * 1024, alias="MAX_UPLOAD_BYTES")
    data_retention_days: int | None = Field(default=None, ge=1, alias="DATA_RETENTION_DAYS")
    enable_job_browser_fallback: bool = Field(default=True, alias="ENABLE_JOB_BROWSER_FALLBACK")
    job_browser_timeout_ms: int = Field(
        default=8000,
        ge=1000,
        le=30000,
        alias="JOB_BROWSER_TIMEOUT_MS",
    )
    jobcopilot_api_token: str | None = Field(default=None, alias="JOBCOPILOT_API_TOKEN")
    openclaw_sender_allowlist_raw: str = Field(default="", alias="OPENCLAW_SENDER_ALLOWLIST")
    auth_required: bool = Field(default=False, alias="AUTH_REQUIRED")
    auth_trusted_proxy_secret: str | None = Field(
        default=None,
        alias="AUTH_TRUSTED_PROXY_SECRET",
    )
    auth_signature_ttl_seconds: int = Field(
        default=300,
        ge=30,
        le=3600,
        alias="AUTH_SIGNATURE_TTL_SECONDS",
    )
    dev_user_external_id: str = Field(
        default="local-dev-user",
        alias="DEV_USER_EXTERNAL_ID",
        min_length=1,
        max_length=255,
    )
    dev_user_email: str | None = Field(default=None, alias="DEV_USER_EMAIL")
    dev_user_display_name: str = Field(
        default="Local Developer",
        alias="DEV_USER_DISPLAY_NAME",
        min_length=1,
        max_length=255,
    )
    dev_user_plan: str = Field(
        default="free",
        alias="DEV_USER_PLAN",
        min_length=1,
        max_length=64,
    )
    dev_user_subscription_status: str = Field(
        default="inactive",
        alias="DEV_USER_SUBSCRIPTION_STATUS",
        min_length=1,
        max_length=64,
    )
    llm_provider: str = Field(default="vertex", alias="LLM_PROVIDER")
    vertex_project_id: str | None = Field(default=None, alias="VERTEX_PROJECT_ID")
    vertex_region: str = Field(default="global", alias="VERTEX_REGION")
    llm_model: str = Field(default="gemini-3.5-flash", alias="LLM_MODEL")
    agent_workflow_mode: AgentWorkflowMode = Field(
        default=AgentWorkflowMode.deterministic_fallback,
        alias="AGENT_WORKFLOW_MODE",
    )
    llm_timeout_seconds: int = Field(default=60, ge=10, le=300, alias="LLM_TIMEOUT_SECONDS")
    llm_temperature: float = Field(default=0.2, ge=0, le=1, alias="LLM_TEMPERATURE")
    llm_max_retries: int = Field(default=2, ge=1, le=5, alias="LLM_MAX_RETRIES")
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
    workflow_inline_execution: bool | None = Field(
        default=None,
        alias="WORKFLOW_INLINE_EXECUTION",
    )
    workflow_worker_poll_seconds: float = Field(
        default=1.0,
        ge=0.1,
        le=30,
        alias="WORKFLOW_WORKER_POLL_SECONDS",
    )
    workflow_job_lease_seconds: int = Field(
        default=180,
        ge=30,
        le=1800,
        alias="WORKFLOW_JOB_LEASE_SECONDS",
    )
    workflow_job_max_attempts: int = Field(
        default=3,
        ge=1,
        le=10,
        alias="WORKFLOW_JOB_MAX_ATTEMPTS",
    )
    workflow_checkpoint_reconcile_seconds: int = Field(
        default=60,
        ge=10,
        le=3600,
        alias="WORKFLOW_CHECKPOINT_RECONCILE_SECONDS",
    )
    usage_reservation_ttl_seconds: int = Field(
        default=900,
        ge=60,
        le=86_400,
        alias="USAGE_RESERVATION_TTL_SECONDS",
    )

    allowed_resume_extensions: frozenset[str] = frozenset(
        {".pdf", ".docx", ".txt", ".md", ".markdown"}
    )

    @field_validator("data_dir")
    @classmethod
    def expand_data_dir(cls, value: Path) -> Path:
        return value.expanduser().resolve()

    @field_validator("data_retention_days", mode="before")
    @classmethod
    def normalize_optional_int(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator(
        "auto_create_db_schema",
        "require_db_migrations",
        "workflow_inline_execution",
        mode="before",
    )
    @classmethod
    def normalize_optional_bool(cls, value: object) -> object:
        if value == "":
            return None
        return value

    @field_validator("app_env")
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized:
            raise ValueError("APP_ENV cannot be empty")
        return normalized

    @field_validator("llm_provider", "vertex_region", "llm_model")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @field_validator("agent_workflow_mode")
    @classmethod
    def reject_retired_workflow_mode(cls, value: AgentWorkflowMode) -> AgentWorkflowMode:
        if value == AgentWorkflowMode.crewai:
            raise ValueError("AGENT_WORKFLOW_MODE=crewai is retired; use langgraph")
        return value

    @field_validator(
        "vertex_project_id",
        "dev_user_email",
        "auth_trusted_proxy_secret",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator(
        "dev_user_external_id",
        "dev_user_display_name",
        "dev_user_plan",
        "dev_user_subscription_status",
    )
    @classmethod
    def normalize_dev_user_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @property
    def debug(self) -> bool:
        return self.app_debug

    @property
    def upload_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def export_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def create_db_schema_on_startup(self) -> bool:
        if self.auto_create_db_schema is not None:
            return self.auto_create_db_schema
        return not self.is_production

    @property
    def check_db_migrations_on_readiness(self) -> bool:
        if self.require_db_migrations is not None:
            return self.require_db_migrations
        return self.is_production

    @property
    def execute_workflow_jobs_inline(self) -> bool:
        if self.workflow_inline_execution is not None:
            return self.workflow_inline_execution
        return not self.is_production

    @property
    def openclaw_sender_allowlist(self) -> list[str]:
        return [
            item.strip() for item in self.openclaw_sender_allowlist_raw.split(",") if item.strip()
        ]


@lru_cache
def get_cached_settings() -> Settings:
    return Settings()

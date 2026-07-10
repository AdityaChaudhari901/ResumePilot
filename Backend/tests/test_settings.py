import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.schemas.agent import AgentWorkflowMode


def test_vertex_llm_settings_are_loaded_from_env_names(tmp_path):
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-test.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        LLM_PROVIDER="vertex",
        VERTEX_PROJECT_ID="alien-slice-499511-f8",
        VERTEX_REGION="global",
        LLM_MODEL="gemini-3.5-flash",
        AGENT_WORKFLOW_MODE="langgraph",
        LLM_TIMEOUT_SECONDS=90,
        LLM_TEMPERATURE=0.1,
        LLM_MAX_RETRIES=3,
        LATEX_COMPILE_TIMEOUT_SECONDS=30,
        LATEX_PDF_MAX_BYTES=10485760,
        DATA_RETENTION_DAYS=30,
        ENABLE_JOB_BROWSER_FALLBACK=False,
        JOB_BROWSER_TIMEOUT_MS=12000,
        AUTH_REQUIRED=True,
        AUTH_TRUSTED_PROXY_SECRET="proxy-secret",
        AUTH_SIGNATURE_TTL_SECONDS=600,
        AUTO_CREATE_DB_SCHEMA=False,
        REQUIRE_DB_MIGRATIONS=True,
        DEV_USER_EXTERNAL_ID="dev-user",
        DEV_USER_EMAIL="dev@example.com",
        DEV_USER_DISPLAY_NAME="Dev User",
        DEV_USER_PLAN="premium",
        DEV_USER_SUBSCRIPTION_STATUS="active",
    )

    assert settings.llm_provider == "vertex"
    assert settings.vertex_project_id == "alien-slice-499511-f8"
    assert settings.vertex_region == "global"
    assert settings.llm_model == "gemini-3.5-flash"
    assert settings.agent_workflow_mode == AgentWorkflowMode.langgraph
    assert settings.llm_timeout_seconds == 90
    assert settings.llm_temperature == 0.1
    assert settings.llm_max_retries == 3
    assert settings.latex_compile_timeout_seconds == 30
    assert settings.latex_pdf_max_bytes == 10485760
    assert settings.data_retention_days == 30
    assert settings.enable_job_browser_fallback is False
    assert settings.job_browser_timeout_ms == 12000
    assert settings.auth_required is True
    assert settings.auth_trusted_proxy_secret == "proxy-secret"
    assert settings.auth_signature_ttl_seconds == 600
    assert settings.auto_create_db_schema is False
    assert settings.require_db_migrations is True
    assert settings.create_db_schema_on_startup is False
    assert settings.check_db_migrations_on_readiness is True
    assert settings.dev_user_external_id == "dev-user"
    assert settings.dev_user_email == "dev@example.com"
    assert settings.dev_user_display_name == "Dev User"
    assert settings.dev_user_plan == "premium"
    assert settings.dev_user_subscription_status == "active"


def test_retired_crewai_runtime_mode_is_rejected(tmp_path):
    with pytest.raises(ValidationError, match="AGENT_WORKFLOW_MODE=crewai is retired"):
        Settings(
            APP_ENV="test",
            DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-test.db'}",
            RESUMEPILOT_DATA_DIR=tmp_path / "data",
            AGENT_WORKFLOW_MODE="crewai",
        )


def test_empty_data_retention_days_disables_retention(tmp_path):
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'resumepilot-test.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        DATA_RETENTION_DAYS="",
    )

    assert settings.data_retention_days is None


def test_production_defaults_disable_schema_creation_and_require_migrations(tmp_path):
    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+psycopg://user:password@example.com:5432/resumepilot",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        AUTH_REQUIRED=True,
        AUTH_TRUSTED_PROXY_SECRET="proxy-secret",
        JOBCOPILOT_API_TOKEN="jobcopilot-token",
    )

    assert settings.create_db_schema_on_startup is False
    assert settings.check_db_migrations_on_readiness is True

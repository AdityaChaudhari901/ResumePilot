from sqlalchemy.engine import make_url

from app.core.config import Settings
from app.schemas.agent import AgentWorkflowMode


class ProductionConfigError(RuntimeError):
    """Raised when production startup would run with unsafe runtime settings."""


def validate_production_settings(settings: Settings) -> None:
    if not settings.is_production:
        return

    errors: list[str] = []
    database_url = make_url(settings.database_url)

    if database_url.drivername.startswith("sqlite"):
        errors.append("DATABASE_URL must use PostgreSQL in production")
    if settings.app_debug:
        errors.append("APP_DEBUG must be false in production")
    if not settings.auth_required:
        errors.append("AUTH_REQUIRED must be true in production")
    if not settings.auth_trusted_proxy_secret:
        errors.append("AUTH_TRUSTED_PROXY_SECRET is required in production")
    elif _is_unsafe_secret(settings.auth_trusted_proxy_secret):
        errors.append(
            "AUTH_TRUSTED_PROXY_SECRET must be a generated secret of at least 32 characters"
        )
    if not settings.jobcopilot_api_token:
        errors.append("JOBCOPILOT_API_TOKEN is required in production")
    elif _is_unsafe_secret(settings.jobcopilot_api_token):
        errors.append("JOBCOPILOT_API_TOKEN must be a generated secret of at least 32 characters")
    if settings.create_db_schema_on_startup:
        errors.append("AUTO_CREATE_DB_SCHEMA must be false in production")
    if not settings.check_db_migrations_on_readiness:
        errors.append("REQUIRE_DB_MIGRATIONS must be true in production")
    if settings.agent_workflow_mode == AgentWorkflowMode.langgraph:
        if settings.llm_provider.strip().lower() != "vertex":
            errors.append("LLM_PROVIDER must be vertex when AGENT_WORKFLOW_MODE=langgraph")
        if not settings.vertex_project_id:
            errors.append("VERTEX_PROJECT_ID is required when AGENT_WORKFLOW_MODE=langgraph")

    if errors:
        raise ProductionConfigError("Unsafe production configuration: " + "; ".join(sorted(errors)))


def _is_unsafe_secret(value: str) -> bool:
    normalized = value.strip().casefold()
    return len(value.strip()) < 32 or normalized.startswith(("change-me", "changeme", "replace-me"))

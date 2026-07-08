from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient

from app.core.config import Settings, get_cached_settings
from app.core.production import ProductionConfigError, validate_production_settings
from app.main import create_app


def test_health_returns_status(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "app": "ResumePilot",
        "environment": "test",
    }


def test_ready_returns_ok_when_database_is_reachable(client):
    response = client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"][0] == {
        "name": "database",
        "status": "ok",
        "detail": "Database connection succeeded.",
    }
    assert body["checks"][1]["name"] == "migrations"
    assert body["checks"][1]["status"] == "skipped"


def test_ready_fails_when_required_migrations_are_missing(tmp_path):
    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=f"sqlite:///{tmp_path / 'missing-migrations.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        REQUIRE_DB_MIGRATIONS=True,
    )
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "failed"
    assert body["checks"][1]["name"] == "migrations"
    assert body["checks"][1]["status"] == "failed"
    assert "does not match Alembic head" in body["checks"][1]["detail"]


def test_ready_passes_after_alembic_upgrade(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'migrated.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("RESUMEPILOT_DATA_DIR", str(tmp_path / "data"))
    get_cached_settings.cache_clear()
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        get_cached_settings.cache_clear()

    settings = Settings(
        APP_ENV="test",
        DATABASE_URL=database_url,
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        AUTO_CREATE_DB_SCHEMA=False,
        REQUIRE_DB_MIGRATIONS=True,
    )
    app = create_app(settings)

    with TestClient(app) as test_client:
        response = test_client.get("/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"][1]["name"] == "migrations"
    assert body["checks"][1]["status"] == "ok"


def test_production_config_rejects_unsafe_runtime_settings(tmp_path):
    settings = Settings(
        APP_ENV="production",
        DATABASE_URL=f"sqlite:///{tmp_path / 'production.db'}",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
    )

    try:
        validate_production_settings(settings)
    except ProductionConfigError as exc:
        detail = str(exc)
    else:
        raise AssertionError("Expected unsafe production settings to be rejected")

    assert "DATABASE_URL must use PostgreSQL in production" in detail
    assert "AUTH_REQUIRED must be true in production" in detail
    assert "AUTH_TRUSTED_PROXY_SECRET is required in production" in detail
    assert "JOBCOPILOT_API_TOKEN is required in production" in detail


def test_production_config_accepts_safe_runtime_settings(tmp_path):
    settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql+psycopg://user:password@example.com:5432/resumepilot",
        RESUMEPILOT_DATA_DIR=tmp_path / "data",
        AUTH_REQUIRED=True,
        AUTH_TRUSTED_PROXY_SECRET="proxy-secret",
        JOBCOPILOT_API_TOKEN="jobcopilot-token",
    )

    validate_production_settings(settings)

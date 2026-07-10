from dataclasses import dataclass
from pathlib import Path

from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.core.config import Settings


@dataclass(frozen=True, slots=True)
class ReadinessCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class ReadinessResult:
    status: str
    checks: list[ReadinessCheck]


def check_application_readiness(engine: Engine, settings: Settings) -> ReadinessResult:
    checks = [
        _check_database_connection(engine),
        _check_migration_state(engine, settings),
    ]
    status = "ok" if all(check.status in {"ok", "skipped"} for check in checks) else "failed"
    return ReadinessResult(status=status, checks=checks)


def _check_database_connection(engine: Engine) -> ReadinessCheck:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except Exception:
        return ReadinessCheck(
            name="database",
            status="failed",
            detail="Database connection failed.",
        )
    return ReadinessCheck(name="database", status="ok", detail="Database connection succeeded.")


def _check_migration_state(engine: Engine, settings: Settings) -> ReadinessCheck:
    if not settings.check_db_migrations_on_readiness:
        return ReadinessCheck(
            name="migrations",
            status="skipped",
            detail="Alembic migration check is disabled for this environment.",
        )

    try:
        script = ScriptDirectory.from_config(_alembic_config())
        expected_heads = set(script.get_heads())
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_heads = set(context.get_current_heads())
    except Exception:
        return ReadinessCheck(
            name="migrations",
            status="failed",
            detail="Migration state could not be verified.",
        )

    if current_heads == expected_heads and expected_heads:
        return ReadinessCheck(
            name="migrations",
            status="ok",
            detail=f"Database revision is at Alembic head {', '.join(sorted(expected_heads))}.",
        )

    current = ", ".join(sorted(current_heads)) if current_heads else "none"
    expected = ", ".join(sorted(expected_heads)) if expected_heads else "none"
    return ReadinessCheck(
        name="migrations",
        status="failed",
        detail=f"Database revision {current} does not match Alembic head {expected}.",
    )


def _alembic_config() -> Config:
    backend_root = Path(__file__).resolve().parents[2]
    config = Config(str(backend_root / "alembic.ini"))
    config.set_main_option("script_location", str(backend_root / "migrations"))
    return config

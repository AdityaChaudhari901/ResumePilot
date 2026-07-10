from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import make_url

from app.core.config import get_cached_settings
from app.db import models  # noqa: F401
from app.db.base import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

LANGGRAPH_CHECKPOINT_TABLES = frozenset(
    {
        "checkpoint_migrations",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
    }
)


def get_url() -> str:
    return get_cached_settings().database_url


def ensure_sqlite_parent_dir(database_url: str) -> None:
    url = make_url(database_url)
    if url.drivername.startswith("sqlite") and url.database not in {None, "", ":memory:"}:
        Path(url.database).expanduser().parent.mkdir(parents=True, exist_ok=True)


def include_application_object(
    object_,
    name: str | None,
    type_: str,
    reflected: bool,
    compare_to,
) -> bool:
    """Keep package-owned LangGraph tables outside Alembic's ownership boundary."""

    del compare_to
    if not reflected:
        return True
    if type_ == "table" and name in LANGGRAPH_CHECKPOINT_TABLES:
        return False
    table = getattr(object_, "table", None)
    return getattr(table, "name", None) not in LANGGRAPH_CHECKPOINT_TABLES


def run_migrations_offline() -> None:
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        include_object=include_application_object,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_url()
    ensure_sqlite_parent_dir(configuration["sqlalchemy.url"])
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_application_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

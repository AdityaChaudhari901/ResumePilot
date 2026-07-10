from __future__ import annotations

import atexit
from collections.abc import Iterator
from contextlib import contextmanager
from threading import Lock
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres import PostgresSaver
from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from sqlalchemy.engine import make_url

from app.core.config import Settings

_MEMORY_SAVERS: dict[str, InMemorySaver] = {}
_MEMORY_SAVERS_LOCK = Lock()
_POSTGRES_POOLS: dict[str, ConnectionPool] = {}
_POSTGRES_POOLS_LOCK = Lock()


def postgres_checkpoint_connection_string(settings: Settings) -> str:
    """Return a psycopg-compatible URL without exposing it to graph state or logs."""

    url = make_url(settings.database_url)
    if not url.drivername.startswith("postgresql"):
        raise ValueError("LangGraph PostgreSQL checkpoints require a PostgreSQL DATABASE_URL")
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


@contextmanager
def open_workflow_checkpointer(settings: Settings) -> Iterator[Any]:
    """Open the production saver or a process-local saver for SQLite tests/development."""

    if settings.database_url.startswith("postgresql"):
        yield PostgresSaver(_postgres_pool(settings))
        return

    with _MEMORY_SAVERS_LOCK:
        saver = _MEMORY_SAVERS.setdefault(settings.database_url, InMemorySaver())
    yield saver


def setup_postgres_checkpointer(settings: Settings) -> None:
    """Apply LangGraph-owned checkpoint migrations once during deployment."""

    connection_string = postgres_checkpoint_connection_string(settings)
    with Connection.connect(
        connection_string,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    ) as connection:
        connection.execute("SELECT pg_advisory_lock(hashtext('resumepilot_langgraph_setup'))")
        try:
            PostgresSaver(connection).setup()
        finally:
            connection.execute("SELECT pg_advisory_unlock(hashtext('resumepilot_langgraph_setup'))")


def delete_workflow_checkpoint(settings: Settings, thread_id: str) -> None:
    """Delete one operation's resumable graph state for privacy or terminal cleanup."""

    with open_workflow_checkpointer(settings) as saver:
        saver.delete_thread(thread_id)


def reconcile_terminal_workflow_checkpoints(settings: Settings) -> int:
    """Delete checkpoint threads whose business job is gone or already terminal."""

    if not settings.database_url.startswith("postgresql"):
        return 0
    connection_string = postgres_checkpoint_connection_string(settings)
    terminal_statuses = ["succeeded", "canceled", "failed", "dead_lettered"]
    with Connection.connect(
        connection_string,
        autocommit=True,
        prepare_threshold=0,
        row_factory=dict_row,
    ) as connection:
        rows = connection.execute(
            """
            WITH checkpoint_threads AS (
                SELECT thread_id FROM checkpoints
                UNION
                SELECT thread_id FROM checkpoint_blobs
                UNION
                SELECT thread_id FROM checkpoint_writes
            )
            SELECT checkpoint_threads.thread_id
            FROM checkpoint_threads
            LEFT JOIN workflow_jobs ON workflow_jobs.id = checkpoint_threads.thread_id
            WHERE workflow_jobs.id IS NULL OR workflow_jobs.status = ANY(%s)
            """,
            (terminal_statuses,),
        ).fetchall()
        saver = PostgresSaver(connection)
        for row in rows:
            saver.delete_thread(str(row["thread_id"]))
    return len(rows)


def reset_ephemeral_checkpointers() -> None:
    """Clear process-local savers between isolated tests."""

    with _MEMORY_SAVERS_LOCK:
        _MEMORY_SAVERS.clear()


def close_workflow_checkpointers() -> None:
    with _POSTGRES_POOLS_LOCK:
        pools = list(_POSTGRES_POOLS.values())
        _POSTGRES_POOLS.clear()
    for pool in pools:
        pool.close()


def _postgres_pool(settings: Settings) -> ConnectionPool:
    connection_string = postgres_checkpoint_connection_string(settings)
    with _POSTGRES_POOLS_LOCK:
        existing = _POSTGRES_POOLS.get(connection_string)
        if existing is not None:
            return existing
        pool = ConnectionPool(
            conninfo=connection_string,
            min_size=0,
            max_size=5,
            open=False,
            kwargs={
                "autocommit": True,
                "prepare_threshold": 0,
                "row_factory": dict_row,
            },
        )
        pool.open()
        _POSTGRES_POOLS[connection_string] = pool
        return pool


atexit.register(close_workflow_checkpointers)

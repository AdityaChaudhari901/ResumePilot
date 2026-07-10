"""Exercise ResumePilot migrations against fresh and prior-release PostgreSQL databases."""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from typing import TypedDict
from uuid import uuid4

import sqlalchemy as sa
from alembic.config import Config
from alembic.script import ScriptDirectory
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt
from sqlalchemy.engine import URL, Engine, make_url
from sqlalchemy.engine.reflection import Inspector
from sqlalchemy.orm import sessionmaker

from app.core.config import Settings
from app.db.models import UsageEventRecord, UserRecord, WorkflowJobRecord
from app.repositories.workflow_jobs import WorkflowJobRepository
from app.services.langgraph_checkpointer import (
    close_workflow_checkpointers,
    open_workflow_checkpointer,
    reconcile_terminal_workflow_checkpoints,
    setup_postgres_checkpointer,
)

BACKEND_ROOT = Path(__file__).resolve().parents[1]
BASELINE_REVISION = "20260709_0007"
FRESH_DATABASE_NAME = "resumepilot_ci_fresh"
UPGRADE_DATABASE_NAME = "resumepilot_ci_upgrade"
REQUIRED_FOREIGN_KEYS = {
    "resumes": ("user_id", "users"),
    "jobs": ("user_id", "users"),
    "analyses": ("user_id", "users"),
    "audit_events": ("user_id", "users"),
}
REQUIRED_INDEXES = {
    "analyses": {"ix_analyses_user_created_id"},
    "applications": {
        "ix_applications_user_updated_id",
        "ix_applications_user_status_updated_id",
    },
    "audit_events": {
        "ix_audit_events_user_created_id",
        "ix_audit_events_user_event_created_id",
    },
    "usage_events": {"ix_usage_events_user_type_state_created"},
    "workflow_jobs": {
        "ix_workflow_jobs_claim",
        "ix_workflow_jobs_stale_lease",
        "ix_workflow_jobs_user_created_id",
    },
}
SEQUENCE_TABLES = (
    "users",
    "resumes",
    "jobs",
    "analyses",
    "audit_events",
    "usage_events",
    "applications",
    "tailored_resume_drafts",
)
SEEDED_IDS = {
    "users": 5000,
    "resumes": 6000,
    "jobs": 7000,
    "analyses": 8000,
    "audit_events": 9000,
    "usage_events": 10000,
    "applications": 11000,
    "tailored_resume_drafts": 12000,
}


class _CheckpointGateState(TypedDict, total=False):
    generation_count: int
    proposal_revision: str
    approval_decision: str


def main() -> None:
    admin_url = _postgres_url(os.environ.get("POSTGRES_ADMIN_URL", ""))
    fresh_url = _database_url(admin_url, FRESH_DATABASE_NAME)
    upgrade_url = _database_url(admin_url, UPGRADE_DATABASE_NAME)

    _recreate_database(admin_url, FRESH_DATABASE_NAME)
    _run_alembic(fresh_url, "upgrade", "head")
    _setup_langgraph(fresh_url)
    _run_alembic(fresh_url, "check")
    _verify_head_schema(fresh_url, expect_seed=False)
    _verify_postgres_job_claiming(fresh_url)
    _verify_langgraph_interrupt_resume(fresh_url)

    _recreate_database(admin_url, UPGRADE_DATABASE_NAME)
    _run_alembic(upgrade_url, "upgrade", BASELINE_REVISION)
    _seed_prior_release(upgrade_url)
    _run_alembic(upgrade_url, "upgrade", "head")
    _setup_langgraph(upgrade_url)
    _run_alembic(upgrade_url, "check")
    _verify_head_schema(upgrade_url, expect_seed=True)

    _run_alembic(upgrade_url, "downgrade", BASELINE_REVISION)
    _verify_baseline_round_trip(upgrade_url)
    _run_alembic(upgrade_url, "upgrade", "head")
    _setup_langgraph(upgrade_url)
    _run_alembic(upgrade_url, "check")
    _verify_head_schema(upgrade_url, expect_seed=True)

    print(
        "PostgreSQL migration gate passed: fresh upgrade, prior-release upgrade, "
        "schema drift check, durable LangGraph interrupt/resume, seed preservation, "
        "sequence advancement, and downgrade round trip."
    )


def _postgres_url(raw_url: str) -> URL:
    if not raw_url:
        raise RuntimeError("POSTGRES_ADMIN_URL is required")
    url = make_url(raw_url)
    if not url.drivername.startswith("postgresql"):
        raise RuntimeError("POSTGRES_ADMIN_URL must use PostgreSQL")
    return url


def _database_url(admin_url: URL, database_name: str) -> str:
    return admin_url.set(database=database_name).render_as_string(hide_password=False)


def _recreate_database(admin_url: URL, database_name: str) -> None:
    engine = sa.create_engine(admin_url, isolation_level="AUTOCOMMIT")
    quoted_name = engine.dialect.identifier_preparer.quote(database_name)
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql(f"DROP DATABASE IF EXISTS {quoted_name} WITH (FORCE)")
            connection.exec_driver_sql(f"CREATE DATABASE {quoted_name}")
    finally:
        engine.dispose()


def _run_alembic(database_url: str, command: str, revision: str | None = None) -> None:
    arguments = [sys.executable, "-m", "alembic", command]
    if revision:
        arguments.append(revision)
    environment = os.environ.copy()
    environment.update(
        {
            "APP_ENV": "test",
            "DATABASE_URL": database_url,
            "RESUMEPILOT_DATA_DIR": str(BACKEND_ROOT / ".local" / "postgres-migration-gate"),
        }
    )
    subprocess.run(arguments, cwd=BACKEND_ROOT, env=environment, check=True)


def _setup_langgraph(database_url: str) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL=database_url)
    setup_postgres_checkpointer(settings)
    setup_postgres_checkpointer(settings)
    engine = sa.create_engine(database_url)
    try:
        tables = set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()
    required = {
        "checkpoint_migrations",
        "checkpoints",
        "checkpoint_blobs",
        "checkpoint_writes",
    }
    missing = required - tables
    if missing:
        raise AssertionError(f"LangGraph checkpoint tables missing: {sorted(missing)}")


def _verify_langgraph_interrupt_resume(database_url: str) -> None:
    settings = Settings(APP_ENV="test", DATABASE_URL=database_url)
    thread_id = str(uuid4())

    with open_workflow_checkpointer(settings) as checkpointer:
        graph = _checkpoint_gate_graph(checkpointer)
        paused = graph.invoke(
            {"generation_count": 0},
            config={"configurable": {"thread_id": thread_id}},
        )
    if not paused.get("__interrupt__") or paused.get("generation_count") != 1:
        raise AssertionError("LangGraph did not persist the expected approval interrupt")

    close_workflow_checkpointers()
    with open_workflow_checkpointer(settings) as checkpointer:
        graph = _checkpoint_gate_graph(checkpointer)
        resumed = graph.invoke(
            Command(
                resume={
                    "decision": "approve",
                    "proposal_revision": paused["proposal_revision"],
                }
            ),
            config={"configurable": {"thread_id": thread_id}},
        )
    if resumed.get("approval_decision") != "approve":
        raise AssertionError("LangGraph approval did not resume after reopening PostgreSQL")
    if resumed.get("generation_count") != 1:
        raise AssertionError("LangGraph reran a completed generation node during resume")

    reconciled = reconcile_terminal_workflow_checkpoints(settings)
    if reconciled < 1:
        raise AssertionError("LangGraph orphan checkpoint reconciliation found no test thread")
    close_workflow_checkpointers()
    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            for table in ("checkpoints", "checkpoint_blobs", "checkpoint_writes"):
                count = connection.scalar(
                    sa.text(f"SELECT COUNT(*) FROM {table} WHERE thread_id = :thread_id"),
                    {"thread_id": thread_id},
                )
                if count:
                    raise AssertionError(f"LangGraph checkpoint cleanup left rows in {table}")
    finally:
        engine.dispose()


def _checkpoint_gate_graph(checkpointer):
    def generate(state: _CheckpointGateState) -> _CheckpointGateState:
        return {
            "generation_count": state.get("generation_count", 0) + 1,
            "proposal_revision": "gate-proposal-v1",
        }

    def await_approval(state: _CheckpointGateState) -> _CheckpointGateState:
        response = interrupt(
            {
                "proposal_revision": state["proposal_revision"],
                "kind": "migration_gate_approval",
            }
        )
        if response.get("proposal_revision") != state["proposal_revision"]:
            raise ValueError("Approval revision mismatch in PostgreSQL migration gate")
        return {"approval_decision": str(response["decision"])}

    builder = StateGraph(_CheckpointGateState)
    builder.add_node("generate", generate)
    builder.add_node("await_approval", await_approval)
    builder.add_edge(START, "generate")
    builder.add_edge("generate", "await_approval")
    builder.add_edge("await_approval", END)
    return builder.compile(checkpointer=checkpointer)


def _seed_prior_release(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO users (
                        id, external_id, email, display_name, plan, stripe_customer_id,
                        subscription_status, created_at, updated_at
                    ) VALUES (
                        :id, 'migration-seed-user', 'seed@example.com', 'Migration Seed',
                        'premium', NULL, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": SEEDED_IDS["users"]},
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO resumes (
                        id, user_id, file_name, file_extension, file_hash, content_type,
                        raw_text, profile_json, candidate_name, candidate_email,
                        created_at, updated_at
                    ) VALUES (
                        :id, :user_id, 'seed.md', '.md', :file_hash, 'text/markdown',
                        'Migration seed resume', CAST(:profile AS JSON), 'Migration Seed',
                        'seed@example.com', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": SEEDED_IDS["resumes"],
                    "user_id": SEEDED_IDS["users"],
                    "file_hash": "a" * 64,
                    "profile": '{"resume_id": 6000}',
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO jobs (
                        id, user_id, source_url, content_hash, company, role, raw_text,
                        profile_json, created_at
                    ) VALUES (
                        :id, :user_id, 'https://example.com/jobs/seed', :content_hash,
                        'Example', 'Engineer', 'Migration seed job', CAST(:profile AS JSON),
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": SEEDED_IDS["jobs"],
                    "user_id": SEEDED_IDS["users"],
                    "content_hash": "b" * 64,
                    "profile": '{"job_id": 7000}',
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO analyses (
                        id, user_id, resume_id, job_id, status, match_score,
                        match_result_json, report_json, report_markdown,
                        validation_warnings_json, workflow_mode, workflow_trace_json,
                        created_at
                    ) VALUES (
                        :id, :user_id, :resume_id, :job_id, 'completed', 80,
                        CAST('{}' AS JSON), CAST('{}' AS JSON), 'seed report',
                        CAST('[]' AS JSON), 'deterministic_fallback', CAST(:trace AS JSON),
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": SEEDED_IDS["analyses"],
                    "user_id": SEEDED_IDS["users"],
                    "resume_id": SEEDED_IDS["resumes"],
                    "job_id": SEEDED_IDS["jobs"],
                    "trace": (
                        '{"mode":"deterministic_fallback","steps":[{"name":'
                        '"validation_gate","status":"completed","summary":"seed"}],'
                        '"validation_warning_codes":[]}'
                    ),
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO audit_events (
                        id, user_id, event_type, request_id, payload_json, created_at
                    ) VALUES (
                        :id, :user_id, 'migration.seeded', 'migration-gate',
                        CAST('{}' AS JSON), CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": SEEDED_IDS["audit_events"], "user_id": SEEDED_IDS["users"]},
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO usage_events (
                        id, user_id, event_type, quantity, cost_estimate_usd,
                        metadata_json, created_at
                    ) VALUES (
                        :id, :user_id, 'analysis_created', 1, NULL,
                        CAST('{}' AS JSON), CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"id": SEEDED_IDS["usage_events"], "user_id": SEEDED_IDS["users"]},
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO applications (
                        id, user_id, source_url, status, company, role,
                        reviewed_job_profile_json, resume_id, job_id, analysis_id,
                        report_id, match_score, created_at, updated_at
                    ) VALUES (
                        :id, :user_id, 'https://example.com/jobs/seed', 'analyzed',
                        'Example', 'Engineer', CAST('{}' AS JSON), :resume_id, :job_id,
                        :analysis_id, :report_id, 80, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": SEEDED_IDS["applications"],
                    "user_id": SEEDED_IDS["users"],
                    "resume_id": SEEDED_IDS["resumes"],
                    "job_id": SEEDED_IDS["jobs"],
                    "analysis_id": SEEDED_IDS["analyses"],
                    "report_id": SEEDED_IDS["analyses"],
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO tailored_resume_drafts (
                        id, user_id, application_id, report_id, status, items_json,
                        created_at, updated_at
                    ) VALUES (
                        :id, :user_id, :application_id, :report_id, 'draft',
                        CAST('[]' AS JSON), CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": SEEDED_IDS["tailored_resume_drafts"],
                    "user_id": SEEDED_IDS["users"],
                    "application_id": SEEDED_IDS["applications"],
                    "report_id": SEEDED_IDS["analyses"],
                },
            )
    finally:
        engine.dispose()


def _verify_head_schema(database_url: str, *, expect_seed: bool) -> None:
    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        _assert_revision(engine, _head_revision())
        _assert_foreign_keys(inspector)
        _assert_resume_unique_constraint(inspector)
        _assert_history_indexes(inspector)
        _assert_workflow_schema(inspector)
        if expect_seed:
            _assert_seed_preserved(engine)
            _assert_seed_backfill(engine)
        _assert_sequences_advanced(engine)
    finally:
        engine.dispose()


def _verify_baseline_round_trip(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        _assert_revision(engine, BASELINE_REVISION)
        _assert_seed_preserved(engine)
        resume_indexes = {index["name"] for index in inspector.get_indexes("resumes")}
        if "uq_resumes_user_file_hash" not in resume_indexes:
            raise AssertionError("Resume uniqueness was not restored as an index on downgrade")
        for table_name, expected_indexes in REQUIRED_INDEXES.items():
            if table_name not in inspector.get_table_names():
                continue
            actual_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
            unexpected = expected_indexes & actual_indexes
            if unexpected:
                raise AssertionError(
                    f"Downgrade left head-only indexes on {table_name}: {sorted(unexpected)}"
                )
    finally:
        engine.dispose()


def _assert_revision(engine: Engine, expected_revision: str) -> None:
    with engine.connect() as connection:
        revision = connection.scalar(sa.text("SELECT version_num FROM alembic_version"))
    if revision != expected_revision:
        raise AssertionError(f"Expected Alembic revision {expected_revision}, found {revision}")


def _head_revision() -> str:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "migrations"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        raise AssertionError(f"Expected one Alembic head, found {heads}")
    return heads[0]


def _assert_foreign_keys(inspector: Inspector) -> None:
    for table_name, (column_name, referred_table) in REQUIRED_FOREIGN_KEYS.items():
        foreign_keys = inspector.get_foreign_keys(table_name)
        if not any(
            foreign_key["constrained_columns"] == [column_name]
            and foreign_key["referred_table"] == referred_table
            for foreign_key in foreign_keys
        ):
            raise AssertionError(f"Missing {table_name}.{column_name} ownership foreign key")


def _assert_resume_unique_constraint(inspector: Inspector) -> None:
    constraints = {
        constraint["name"]: constraint["column_names"]
        for constraint in inspector.get_unique_constraints("resumes")
    }
    if constraints.get("uq_resumes_user_file_hash") != ["user_id", "file_hash"]:
        raise AssertionError("Resume tenant/hash uniqueness is not a database constraint")


def _assert_history_indexes(inspector: Inspector) -> None:
    for table_name, expected_indexes in REQUIRED_INDEXES.items():
        actual_indexes = {index["name"] for index in inspector.get_indexes(table_name)}
        missing = expected_indexes - actual_indexes
        if missing:
            raise AssertionError(f"Missing {table_name} history indexes: {sorted(missing)}")


def _assert_workflow_schema(inspector: Inspector) -> None:
    workflow_foreign_keys = inspector.get_foreign_keys("workflow_jobs")
    expected_workflow_foreign_keys = {
        (("user_id",), "users"),
        (("usage_event_id",), "usage_events"),
    }
    actual_workflow_foreign_keys = {
        (tuple(foreign_key["constrained_columns"]), foreign_key["referred_table"])
        for foreign_key in workflow_foreign_keys
    }
    if not expected_workflow_foreign_keys <= actual_workflow_foreign_keys:
        raise AssertionError("Workflow job ownership/usage foreign keys are incomplete")

    analysis_foreign_keys = inspector.get_foreign_keys("analyses")
    if not any(
        foreign_key["constrained_columns"] == ["workflow_job_id"]
        and foreign_key["referred_table"] == "workflow_jobs"
        for foreign_key in analysis_foreign_keys
    ):
        raise AssertionError("Analysis workflow-job foreign key is missing")

    workflow_uniques = {
        constraint["name"]: constraint["column_names"]
        for constraint in inspector.get_unique_constraints("workflow_jobs")
    }
    if workflow_uniques.get("uq_workflow_jobs_user_kind_idempotency") != [
        "user_id",
        "kind",
        "idempotency_key_hash",
    ]:
        raise AssertionError("Workflow idempotency uniqueness is missing")


def _assert_seed_backfill(engine: Engine) -> None:
    with engine.connect() as connection:
        application = (
            connection.execute(
                sa.text(
                    "SELECT source_type, reviewed_job_text, source_content_hash "
                    "FROM applications WHERE id = :id"
                ),
                {"id": SEEDED_IDS["applications"]},
            )
            .mappings()
            .one()
        )
        if application["source_type"] != "url":
            raise AssertionError("Legacy URL application source type was not backfilled")
        if application["reviewed_job_text"] != "Migration seed job":
            raise AssertionError("Legacy application did not preserve the linked job snapshot")
        expected_hash = hashlib.sha256(b"Migration seed job").hexdigest()
        if application["source_content_hash"] != expected_hash:
            raise AssertionError("Legacy application source hash was not backfilled")

        usage_state = connection.scalar(
            sa.text("SELECT state FROM usage_events WHERE id = :id"),
            {"id": SEEDED_IDS["usage_events"]},
        )
        if usage_state != "consumed":
            raise AssertionError("Legacy completed usage was not backfilled as consumed")


def _verify_postgres_job_claiming(database_url: str) -> None:
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    job_id = str(uuid4())
    now = datetime.now(UTC)
    with session_factory() as db:
        user = UserRecord(
            external_id=f"migration-queue-{job_id}",
            plan="premium",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        usage = UsageEventRecord(
            user_id=user.id,
            event_type="analysis_created",
            quantity=1,
            metadata_json={"status": "reserved"},
            state="reserved",
            reservation_key=job_id,
            reserved_at=now,
        )
        db.add(usage)
        db.flush()
        db.add(
            WorkflowJobRecord(
                id=job_id,
                user_id=user.id,
                kind="analysis",
                status="queued",
                idempotency_key_hash="c" * 64,
                request_fingerprint="d" * 64,
                payload_json={"resume_id": 1, "job_text": "migration gate placeholder"},
                stage="queued",
                progress_percent=0,
                attempt_count=0,
                max_attempts=3,
                priority=0,
                available_at=now,
                usage_event_id=usage.id,
                result_json={},
            )
        )
        db.commit()

    barrier = Barrier(2)

    def claim(worker_id: str) -> str | None:
        with session_factory() as db:
            barrier.wait(timeout=10)
            claimed = WorkflowJobRepository(db).claim_next(
                worker_id=worker_id,
                lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
            return claimed.id if claimed else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        claimed_ids = list(executor.map(claim, ("postgres-gate-a", "postgres-gate-b")))
    if claimed_ids.count(job_id) != 1 or claimed_ids.count(None) != 1:
        raise AssertionError(f"SKIP LOCKED claim was not exclusive: {claimed_ids}")

    with session_factory() as db:
        record = WorkflowJobRepository(db).get_any(job_id)
        if record is None:
            raise AssertionError("Claimed workflow job disappeared")
        record.status = "running"
        record.lease_expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.add(record)
        db.commit()
    with session_factory() as db:
        recovered = WorkflowJobRepository(db).claim_next(
            worker_id="postgres-gate-recovery",
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        if recovered is None or recovered.id != job_id or recovered.attempt_count != 2:
            raise AssertionError("Expired workflow lease was not recovered exactly once")
    engine.dispose()


def _assert_seed_preserved(engine: Engine) -> None:
    with engine.connect() as connection:
        for table_name, record_id in SEEDED_IDS.items():
            table = sa.table(table_name, sa.column("id", sa.Integer()))
            count = connection.scalar(
                sa.select(sa.func.count()).select_from(table).where(table.c.id == record_id)
            )
            if count != 1:
                raise AssertionError(f"Seed row {table_name}.{record_id} was not preserved")


def _assert_sequences_advanced(engine: Engine) -> None:
    with engine.connect() as connection:
        for table_name in SEQUENCE_TABLES:
            table = sa.table(table_name, sa.column("id", sa.Integer()))
            max_id = connection.scalar(sa.select(sa.func.max(table.c.id)))
            next_id = connection.scalar(
                sa.text("SELECT nextval(pg_get_serial_sequence(:table_name, 'id'))"),
                {"table_name": table_name},
            )
            if max_id is not None and (next_id is None or next_id <= max_id):
                raise AssertionError(
                    f"Sequence for {table_name}.id returned {next_id} after maximum {max_id}"
                )


if __name__ == "__main__":
    main()

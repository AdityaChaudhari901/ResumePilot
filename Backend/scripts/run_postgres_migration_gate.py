"""Exercise ResumePilot migrations against fresh and prior-release PostgreSQL databases."""

from __future__ import annotations

import hashlib
import json
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
from app.db.models import (
    AnalysisRecord,
    ApplicationRecord,
    AuditEventRecord,
    JobRecord,
    ResumeRecord,
    UsageEventRecord,
    UserRecord,
    WorkflowJobRecord,
)
from app.repositories.workflow_jobs import WorkflowJobRepository
from app.schemas.auth import CurrentUser
from app.schemas.job import JobAnalysisRequest
from app.schemas.match import MatchScoreBreakdown
from app.services.analysis_finalization_service import finalize_analysis_transaction
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
        "uq_workflow_jobs_active_analysis_application",
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
ROLLBACK_V2_WORKFLOW_ID = "33333333-3333-4333-8333-333333333333"
ROLLBACK_V2_USAGE_ID = 10003
ROLLBACK_DELETE_ANALYSIS_ID = 8001


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
    _verify_active_analysis_uniqueness(fresh_url)
    _verify_postgres_job_claiming(fresh_url)
    _verify_incompatible_worker_fence(fresh_url)
    _verify_analysis_finalization_concurrency(fresh_url)
    _verify_langgraph_interrupt_resume(fresh_url)

    _recreate_database(admin_url, UPGRADE_DATABASE_NAME)
    _run_alembic(upgrade_url, "upgrade", BASELINE_REVISION)
    _seed_prior_release(upgrade_url)
    _run_alembic(upgrade_url, "upgrade", "head")
    _setup_langgraph(upgrade_url)
    _run_alembic(upgrade_url, "check")
    _verify_head_schema(upgrade_url, expect_seed=True)
    _verify_old_writer_analysis_default(upgrade_url)

    _seed_v2_rollback_contract(upgrade_url)
    _assert_active_v2_downgrade_guard(upgrade_url)
    _run_alembic(upgrade_url, "downgrade", "20260710_0009")
    _run_alembic(upgrade_url, "upgrade", "head")
    _verify_v2_rollback_round_trip(upgrade_url)

    _run_alembic(upgrade_url, "downgrade", "20260710_0009")
    _assert_deep_score_downgrade_guard(upgrade_url)
    _delete_rollback_privacy_fixture(upgrade_url)
    _seed_score_version_upgrade(upgrade_url)
    _run_alembic(upgrade_url, "upgrade", "head")
    _verify_score_version_upgrade(upgrade_url)

    _run_alembic(upgrade_url, "downgrade", BASELINE_REVISION)
    _verify_baseline_round_trip(upgrade_url)
    _run_alembic(upgrade_url, "upgrade", "head")
    _setup_langgraph(upgrade_url)
    _run_alembic(upgrade_url, "check")
    _verify_head_schema(upgrade_url, expect_seed=True)

    print(
        "PostgreSQL migration gate passed: fresh upgrade, prior-release upgrade, "
        "score-version backfill, provenance-preserving rollback, schema drift check, "
        "atomic active-analysis uniqueness, concurrent analysis finalization, "
        "durable LangGraph interrupt/resume, seed preservation, sequence advancement, and "
        "downgrade round trip."
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
        _assert_score_contract_schema(inspector)
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
    workflow_columns = {column["name"] for column in inspector.get_columns("workflow_jobs")}
    if "application_id" not in workflow_columns:
        raise AssertionError("Workflow job application provenance column is missing")

    workflow_indexes = {index["name"]: index for index in inspector.get_indexes("workflow_jobs")}
    active_analysis_index = workflow_indexes.get("uq_workflow_jobs_active_analysis_application")
    if (
        active_analysis_index is None
        or not active_analysis_index.get("unique")
        or active_analysis_index.get("column_names") != ["user_id", "application_id"]
    ):
        raise AssertionError("Active analysis/application uniqueness is missing")

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
    workflow_checks = {
        constraint["name"] for constraint in inspector.get_check_constraints("workflow_jobs")
    }
    if "ck_workflow_jobs_evidence_v2_worker" not in workflow_checks:
        raise AssertionError("Evidence v2 worker compatibility constraint is missing")


def _assert_score_contract_schema(inspector: Inspector) -> None:
    expected_columns = {
        "analyses": {"scoring_version", "score_status", "score_breakdown_json"},
        "applications": {"scoring_version", "score_status"},
        "workflow_jobs": {"scoring_version"},
    }
    for table_name, expected in expected_columns.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = expected - actual
        if missing:
            raise AssertionError(f"Missing {table_name} score-contract columns: {sorted(missing)}")

    analysis_columns = {column["name"]: column for column in inspector.get_columns("analyses")}
    scoring_default = str(analysis_columns["scoring_version"].get("default") or "")
    if "deterministic_v1" not in scoring_default:
        raise AssertionError("Old-writer analysis fallback is not deterministic_v1")


def _verify_old_writer_analysis_default(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    old_writer_analysis_id = 8002
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO analyses (
                        id, user_id, resume_id, job_id, status, match_score,
                        match_result_json, report_json, report_markdown,
                        validation_warnings_json, workflow_mode, workflow_trace_json,
                        created_at
                    ) VALUES (
                        :id, :user_id, :resume_id, :job_id, 'completed', 50,
                        CAST('{}' AS JSON), CAST('{}' AS JSON), 'old writer report',
                        CAST('[]' AS JSON), 'deterministic_fallback', CAST('{}' AS JSON),
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": old_writer_analysis_id,
                    "user_id": SEEDED_IDS["users"],
                    "resume_id": SEEDED_IDS["resumes"],
                    "job_id": SEEDED_IDS["jobs"],
                },
            )
            scoring_version = connection.scalar(
                sa.text("SELECT scoring_version FROM analyses WHERE id = :id"),
                {"id": old_writer_analysis_id},
            )
            if scoring_version != "deterministic_v1":
                raise AssertionError("Old writer analysis did not receive deterministic v1")
            connection.execute(
                sa.text("DELETE FROM analyses WHERE id = :id"),
                {"id": old_writer_analysis_id},
            )
    finally:
        engine.dispose()


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

        analysis_score_contract = (
            connection.execute(
                sa.text(
                    "SELECT scoring_version, score_status, score_breakdown_json "
                    "FROM analyses WHERE id = :id"
                ),
                {"id": SEEDED_IDS["analyses"]},
            )
            .mappings()
            .one()
        )
        if analysis_score_contract["scoring_version"] != "legacy_unversioned":
            raise AssertionError("Historical analysis score version was not preserved as legacy")
        if analysis_score_contract["score_status"] != "scored":
            raise AssertionError("Historical analysis score status was not backfilled")
        if analysis_score_contract["score_breakdown_json"] is not None:
            raise AssertionError("Historical analysis received an invented score breakdown")

        application_score_contract = (
            connection.execute(
                sa.text("SELECT scoring_version, score_status FROM applications WHERE id = :id"),
                {"id": SEEDED_IDS["applications"]},
            )
            .mappings()
            .one()
        )
        if application_score_contract["scoring_version"] != "legacy_unversioned":
            raise AssertionError("Historical application score version was not backfilled")
        if application_score_contract["score_status"] != "scored":
            raise AssertionError("Historical application score status was not backfilled")


def _seed_score_version_upgrade(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    linked_job_id = "11111111-1111-4111-8111-111111111111"
    queued_job_id = "22222222-2222-4222-8222-222222222222"
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    """
                    INSERT INTO usage_events (
                        id, user_id, event_type, quantity, cost_estimate_usd,
                        metadata_json, state, reservation_key, reserved_at, settled_at,
                        created_at
                    ) VALUES
                        (10001, :user_id, 'analysis_created', 1, NULL, CAST('{}' AS JSON),
                         'consumed', :linked_job_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP),
                        (10002, :user_id, 'analysis_created', 1, NULL, CAST('{}' AS JSON),
                         'reserved', :queued_job_id, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP)
                    """
                ),
                {
                    "user_id": SEEDED_IDS["users"],
                    "linked_job_id": linked_job_id,
                    "queued_job_id": queued_job_id,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO workflow_jobs (
                        id, user_id, kind, status, idempotency_key_hash,
                        request_fingerprint, payload_json, stage, progress_percent,
                        attempt_count, max_attempts, priority, available_at, lease_owner,
                        lease_expires_at, heartbeat_at, cancel_requested_at, usage_event_id,
                        analysis_id, result_json, error_code, error_message, request_id,
                        created_at, updated_at, started_at, finished_at
                    ) VALUES
                        (:linked_job_id, :user_id, 'analysis', 'succeeded', :linked_hash,
                         :linked_fingerprint, CAST('{}' AS JSON), 'completed', 100, 1, 3, 0,
                         CURRENT_TIMESTAMP, NULL, NULL, NULL, NULL, 10001, :analysis_id,
                         CAST('{}' AS JSON), NULL, NULL, NULL, CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP),
                        (:queued_job_id, :user_id, 'analysis', 'queued', :queued_hash,
                         :queued_fingerprint, CAST('{}' AS JSON), 'queued', 0, 0, 3, 0,
                         CURRENT_TIMESTAMP, NULL, NULL, NULL, NULL, 10002, NULL,
                         CAST('{}' AS JSON), NULL, NULL, NULL, CURRENT_TIMESTAMP,
                         CURRENT_TIMESTAMP, NULL, NULL)
                    """
                ),
                {
                    "linked_job_id": linked_job_id,
                    "queued_job_id": queued_job_id,
                    "user_id": SEEDED_IDS["users"],
                    "analysis_id": SEEDED_IDS["analyses"],
                    "linked_hash": "c" * 64,
                    "linked_fingerprint": "d" * 64,
                    "queued_hash": "e" * 64,
                    "queued_fingerprint": "f" * 64,
                },
            )
            connection.execute(
                sa.text("UPDATE analyses SET workflow_job_id = :job_id WHERE id = :analysis_id"),
                {"job_id": linked_job_id, "analysis_id": SEEDED_IDS["analyses"]},
            )
    finally:
        engine.dispose()


def _seed_v2_rollback_contract(database_url: str) -> None:
    breakdown = MatchScoreBreakdown.model_validate(
        {
            "scoring_version": "evidence_v2",
            "score_status": "scored",
            "uncapped_score": 80,
            "score_cap": None,
            "total_score": 80,
            "components": [
                {
                    "key": "required_skills",
                    "status": "scored",
                    "score": 80,
                    "base_weight": 50,
                    "effective_weight": 100,
                    "contribution": 80,
                    "matched_count": 1,
                    "total_count": 1,
                    "evidence_ids": ["migration_seed_001"],
                    "explanation": "Migration rollback seed required-skill evidence.",
                },
                *[
                    {
                        "key": key,
                        "status": "not_applicable",
                        "score": None,
                        "base_weight": weight,
                        "effective_weight": 0,
                        "contribution": 0,
                        "matched_count": None,
                        "total_count": None,
                        "evidence_ids": [],
                        "explanation": "Migration rollback seed does not use this component.",
                    }
                    for key, weight in (
                        ("responsibilities", 20),
                        ("preferred_skills", 10),
                        ("experience", 15),
                        ("domain", 5),
                        ("evidence_strength", 0),
                    )
                ],
            ],
        }
    )
    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE analyses SET scoring_version = 'evidence_v2', "
                    "score_status = 'scored', score_breakdown_json = CAST(:breakdown AS JSON) "
                    "WHERE id = :analysis_id"
                ),
                {
                    "analysis_id": SEEDED_IDS["analyses"],
                    "breakdown": json.dumps(breakdown.model_dump(mode="json")),
                },
            )
            connection.execute(
                sa.text(
                    "UPDATE applications SET scoring_version = 'evidence_v2', "
                    "score_status = 'scored' WHERE id = :application_id"
                ),
                {"application_id": SEEDED_IDS["applications"]},
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO analyses (
                        id, user_id, resume_id, job_id, workflow_job_id, status, match_score,
                        scoring_version, score_status, score_breakdown_json, match_result_json,
                        report_json, report_markdown, validation_warnings_json, workflow_mode,
                        workflow_trace_json, created_at
                    )
                    SELECT :new_id, user_id, resume_id, job_id, NULL, status, match_score,
                        scoring_version, score_status, score_breakdown_json, match_result_json,
                        report_json, report_markdown, validation_warnings_json, workflow_mode,
                        workflow_trace_json, CURRENT_TIMESTAMP
                    FROM analyses WHERE id = :source_id
                    """
                ),
                {
                    "new_id": ROLLBACK_DELETE_ANALYSIS_ID,
                    "source_id": SEEDED_IDS["analyses"],
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO usage_events (
                        id, user_id, event_type, quantity, cost_estimate_usd,
                        metadata_json, state, reservation_key, reserved_at, settled_at,
                        created_at
                    ) VALUES (
                        :id, :user_id, 'analysis_created', 1, NULL, CAST('{}' AS JSON),
                        'reserved', :workflow_id, CURRENT_TIMESTAMP, NULL, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {
                    "id": ROLLBACK_V2_USAGE_ID,
                    "user_id": SEEDED_IDS["users"],
                    "workflow_id": ROLLBACK_V2_WORKFLOW_ID,
                },
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO workflow_jobs (
                        id, user_id, kind, status, idempotency_key_hash,
                        request_fingerprint, payload_json, scoring_version, stage,
                        progress_percent, attempt_count, max_attempts, priority, available_at,
                        lease_owner, lease_expires_at, heartbeat_at, cancel_requested_at,
                        usage_event_id, analysis_id, result_json, error_code, error_message,
                        request_id, created_at, updated_at, started_at, finished_at
                    ) VALUES (
                        :id, :user_id, 'analysis', 'queued', :key_hash, :fingerprint,
                        CAST('{}' AS JSON), 'evidence_v2', 'queued', 0, 0, 3, 0,
                        CURRENT_TIMESTAMP, NULL, NULL, NULL, NULL, :usage_id, NULL,
                        CAST('{}' AS JSON), NULL, NULL, NULL, CURRENT_TIMESTAMP,
                        CURRENT_TIMESTAMP, NULL, NULL
                    )
                    """
                ),
                {
                    "id": ROLLBACK_V2_WORKFLOW_ID,
                    "user_id": SEEDED_IDS["users"],
                    "key_hash": "7" * 64,
                    "fingerprint": "8" * 64,
                    "usage_id": ROLLBACK_V2_USAGE_ID,
                },
            )
    finally:
        engine.dispose()


def _assert_active_v2_downgrade_guard(database_url: str) -> None:
    try:
        _run_alembic(database_url, "downgrade", "20260710_0009")
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError("Active evidence_v2 workflow did not block schema downgrade")

    engine = sa.create_engine(database_url)
    try:
        _assert_revision(engine, _head_revision())
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE workflow_jobs SET status = 'failed', stage = 'failed', "
                    "finished_at = CURRENT_TIMESTAMP WHERE id = :workflow_id"
                ),
                {"workflow_id": ROLLBACK_V2_WORKFLOW_ID},
            )
    finally:
        engine.dispose()


def _assert_deep_score_downgrade_guard(database_url: str) -> None:
    try:
        _run_alembic(database_url, "downgrade", BASELINE_REVISION)
    except subprocess.CalledProcessError:
        pass
    else:
        raise AssertionError("Evidence v2 provenance did not block a destructive deep downgrade")

    engine = sa.create_engine(database_url)
    try:
        _assert_revision(engine, "20260710_0009")
        inspector = sa.inspect(engine)
        expected_sidecars = {
            "score_contract_0010_analysis_rollback",
            "score_contract_0010_workflow_rollback",
        }
        if not expected_sidecars <= set(inspector.get_table_names()):
            raise AssertionError("Blocked deep downgrade did not retain score rollback sidecars")
    finally:
        engine.dispose()


def _delete_rollback_privacy_fixture(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text("DELETE FROM analyses WHERE id = :analysis_id"),
                {"analysis_id": ROLLBACK_DELETE_ANALYSIS_ID},
            )
            connection.execute(
                sa.text("DELETE FROM workflow_jobs WHERE id = :workflow_id"),
                {"workflow_id": ROLLBACK_V2_WORKFLOW_ID},
            )
            analysis_backup_count = connection.scalar(
                sa.text(
                    "SELECT COUNT(*) FROM score_contract_0010_analysis_rollback "
                    "WHERE analysis_id = :analysis_id"
                ),
                {"analysis_id": ROLLBACK_DELETE_ANALYSIS_ID},
            )
            workflow_backup_count = connection.scalar(
                sa.text(
                    "SELECT COUNT(*) FROM score_contract_0010_workflow_rollback "
                    "WHERE workflow_job_id = :workflow_id"
                ),
                {"workflow_id": ROLLBACK_V2_WORKFLOW_ID},
            )
        if analysis_backup_count or workflow_backup_count:
            raise AssertionError("Rollback sidecars retained deleted tenant score metadata")
    finally:
        engine.dispose()


def _verify_v2_rollback_round_trip(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    try:
        inspector = sa.inspect(engine)
        with engine.connect() as connection:
            analysis = (
                connection.execute(
                    sa.text(
                        "SELECT scoring_version, score_status, score_breakdown_json "
                        "FROM analyses WHERE id = :analysis_id"
                    ),
                    {"analysis_id": SEEDED_IDS["analyses"]},
                )
                .mappings()
                .one()
            )
            application_version = connection.scalar(
                sa.text("SELECT scoring_version FROM applications WHERE id = :application_id"),
                {"application_id": SEEDED_IDS["applications"]},
            )
            workflow_version = connection.scalar(
                sa.text("SELECT scoring_version FROM workflow_jobs WHERE id = :workflow_id"),
                {"workflow_id": ROLLBACK_V2_WORKFLOW_ID},
            )
        if analysis["scoring_version"] != "evidence_v2":
            raise AssertionError("Rollback round trip lost the analysis scoring version")
        if analysis["score_status"] != "scored":
            raise AssertionError("Rollback round trip lost the analysis score status")
        if analysis["score_breakdown_json"]["total_score"] != 80:
            raise AssertionError("Rollback round trip lost the analysis score breakdown")
        if application_version != "evidence_v2":
            raise AssertionError("Rollback round trip lost linked application provenance")
        if workflow_version != "evidence_v2":
            raise AssertionError("Rollback round trip lost the terminal workflow scorer snapshot")
        rollback_tables = {
            "score_contract_0010_analysis_rollback",
            "score_contract_0010_workflow_rollback",
        }
        if rollback_tables & set(inspector.get_table_names()):
            raise AssertionError("Rollback sidecar tables were not removed after restoration")
    finally:
        engine.dispose()


def _verify_score_version_upgrade(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    try:
        with engine.connect() as connection:
            analysis_version = connection.scalar(
                sa.text("SELECT scoring_version FROM analyses WHERE id = :id"),
                {"id": SEEDED_IDS["analyses"]},
            )
            application_version = connection.scalar(
                sa.text("SELECT scoring_version FROM applications WHERE id = :id"),
                {"id": SEEDED_IDS["applications"]},
            )
            workflow_versions = dict(
                connection.execute(
                    sa.text("SELECT id, scoring_version FROM workflow_jobs WHERE kind = 'analysis'")
                ).all()
            )
            deleted_analysis_count = connection.scalar(
                sa.text("SELECT COUNT(*) FROM analyses WHERE id = :analysis_id"),
                {"analysis_id": ROLLBACK_DELETE_ANALYSIS_ID},
            )
        if analysis_version != "deterministic_v1":
            raise AssertionError("Workflow-linked analysis did not retain deterministic v1")
        if application_version != "deterministic_v1":
            raise AssertionError("Linked application did not inherit its analysis score version")
        expected_versions = {
            "11111111-1111-4111-8111-111111111111": "deterministic_v1",
            "22222222-2222-4222-8222-222222222222": "deterministic_v1",
        }
        if workflow_versions != expected_versions:
            raise AssertionError(
                f"Queued and completed workflows were not versioned safely: {workflow_versions}"
            )
        if deleted_analysis_count:
            raise AssertionError("Re-upgrade resurrected deleted tenant score metadata")
    finally:
        engine.dispose()


def _verify_active_analysis_uniqueness(database_url: str) -> None:
    engine = sa.create_engine(database_url)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    operation_ids = (
        "00000000-0000-4000-8000-000000009301",
        "00000000-0000-4000-8000-000000009302",
    )
    replacement_operation_id = "00000000-0000-4000-8000-000000009303"
    application_id = 9303
    try:
        with session_factory() as db:
            user = UserRecord(
                external_id=f"active-analysis-gate-{uuid4()}",
                display_name="Active analysis gate",
                plan="premium",
                subscription_status="active",
            )
            db.add(user)
            db.flush()
            user_id = user.id
            usages = [
                UsageEventRecord(
                    user_id=user_id,
                    event_type="analysis_created",
                    state="reserved",
                    reservation_key=operation_id,
                    reserved_at=datetime.now(UTC),
                    metadata_json={"status": "reserved"},
                )
                for operation_id in operation_ids
            ]
            db.add_all(usages)
            db.commit()
            usage_ids = [usage.id for usage in usages]

        barrier = Barrier(2)

        def insert_active_operation(operation_id: str, usage_id: int) -> str:
            with session_factory() as db:
                now = datetime.now(UTC)
                db.add(
                    WorkflowJobRecord(
                        id=operation_id,
                        user_id=user_id,
                        kind="analysis",
                        status="queued",
                        idempotency_key_hash=hashlib.sha256(operation_id.encode()).hexdigest(),
                        request_fingerprint=hashlib.sha256(
                            f"request:{operation_id}".encode()
                        ).hexdigest(),
                        payload_json={"application_id": application_id},
                        scoring_version="evidence_v2",
                        stage="queued",
                        progress_percent=0,
                        attempt_count=0,
                        max_attempts=3,
                        priority=0,
                        available_at=now,
                        usage_event_id=usage_id,
                        application_id=application_id,
                        result_json={},
                        created_at=now,
                        updated_at=now,
                    )
                )
                barrier.wait(timeout=10)
                try:
                    db.commit()
                except sa.exc.IntegrityError:
                    db.rollback()
                    return "conflict"
                return "created"

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(insert_active_operation, operation_id, usage_id)
                for operation_id, usage_id in zip(operation_ids, usage_ids, strict=True)
            ]
            results = sorted(future.result(timeout=20) for future in futures)
        if results != ["conflict", "created"]:
            raise AssertionError(f"Expected one active-analysis conflict, found {results}")

        with session_factory() as db:
            active = list(
                db.scalars(
                    sa.select(WorkflowJobRecord).where(
                        WorkflowJobRecord.user_id == user_id,
                        WorkflowJobRecord.application_id == application_id,
                        WorkflowJobRecord.status == "queued",
                    )
                )
            )
            if len(active) != 1:
                raise AssertionError("Active-analysis index did not preserve exactly one winner")
            active[0].status = "succeeded"
            active[0].stage = "completed"
            active[0].finished_at = datetime.now(UTC)
            replacement_usage = UsageEventRecord(
                user_id=user_id,
                event_type="analysis_created",
                state="reserved",
                reservation_key=replacement_operation_id,
                reserved_at=datetime.now(UTC),
                metadata_json={"status": "reserved"},
            )
            db.add(replacement_usage)
            db.flush()
            now = datetime.now(UTC)
            db.add(
                WorkflowJobRecord(
                    id=replacement_operation_id,
                    user_id=user_id,
                    kind="analysis",
                    status="queued",
                    idempotency_key_hash="9" * 64,
                    request_fingerprint="8" * 64,
                    payload_json={"application_id": application_id},
                    scoring_version="evidence_v2",
                    stage="queued",
                    progress_percent=0,
                    attempt_count=0,
                    max_attempts=3,
                    priority=0,
                    available_at=now,
                    usage_event_id=replacement_usage.id,
                    application_id=application_id,
                    result_json={},
                    created_at=now,
                    updated_at=now,
                )
            )
            db.commit()

            db.execute(sa.delete(WorkflowJobRecord).where(WorkflowJobRecord.user_id == user_id))
            db.execute(sa.delete(UsageEventRecord).where(UsageEventRecord.user_id == user_id))
            db.execute(sa.delete(UserRecord).where(UserRecord.id == user_id))
            db.commit()
    finally:
        engine.dispose()


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


def _verify_incompatible_worker_fence(database_url: str) -> None:
    engine = sa.create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    job_id = str(uuid4())
    now = datetime.now(UTC)
    with session_factory() as db:
        user = UserRecord(
            external_id=f"worker-fence-{job_id}",
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
                idempotency_key_hash="9" * 64,
                request_fingerprint="a" * 64,
                payload_json={"resume_id": 1, "job_text": "worker fence placeholder"},
                scoring_version="evidence_v2",
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

    try:
        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE workflow_jobs SET status = 'running', lease_owner = 'old-worker' "
                    "WHERE id = :job_id"
                ),
                {"job_id": job_id},
            )
    except sa.exc.IntegrityError:
        pass
    else:
        raise AssertionError("An incompatible worker claimed an evidence_v2 workflow")

    with session_factory() as db:
        claimed = WorkflowJobRepository(db).claim_by_id(
            job_id,
            worker_id="postgres-compatible-worker",
            lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        )
        if claimed is None or claimed.lease_owner != "score-v2:postgres-compatible-worker":
            raise AssertionError("Compatible worker did not claim the evidence_v2 workflow")
    engine.dispose()


def _verify_analysis_finalization_concurrency(database_url: str) -> None:
    """Prove PostgreSQL serializes replay repair into one complete finalization."""

    engine = sa.create_engine(database_url, pool_pre_ping=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    seed_key = str(uuid4())
    job_text = (
        "Role: Backend Engineer. Company: Finalization Gate. Required Python, "
        "PostgreSQL, transaction safety, and automated testing experience."
    )
    with session_factory() as db:
        user = UserRecord(
            external_id=f"finalization-gate-{seed_key}",
            email="finalization-gate@example.com",
            display_name="Finalization Gate",
            plan="premium",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        resume = ResumeRecord(
            user_id=user.id,
            file_name="finalization-gate.txt",
            file_extension=".txt",
            file_hash=hashlib.sha256(seed_key.encode()).hexdigest(),
            content_type="text/plain",
            raw_text="Backend engineer with Python and PostgreSQL experience.",
            profile_json={"resume_id": 0},
            candidate_name="Finalization Gate",
            candidate_email="finalization-gate@example.com",
        )
        db.add(resume)
        db.flush()
        job = JobRecord(
            user_id=user.id,
            source_url=None,
            content_hash=hashlib.sha256(job_text.encode()).hexdigest(),
            company="Finalization Gate",
            role="Backend Engineer",
            raw_text=job_text,
            profile_json={"job_id": 0},
        )
        db.add(job)
        db.flush()
        analysis = AnalysisRecord(
            user_id=user.id,
            resume_id=resume.id,
            job_id=job.id,
            status="completed",
            match_score=91.0,
            match_result_json={
                "score": 91.0,
                "required_skill_score": 91.0,
                "preferred_skill_score": 91.0,
                "responsibility_alignment_score": 91.0,
                "experience_level_score": 91.0,
                "domain_keyword_score": 91.0,
                "resume_quality_score": 91.0,
                "matched_skills": [],
                "missing_skills": [],
                "weak_skills": [],
                "confidence": "medium",
            },
            report_json={
                "analysis_id": 0,
                "resume_id": resume.id,
                "job_id": job.id,
                "executive_summary": "PostgreSQL concurrency finalization gate.",
                "match_score": 91.0,
                "matched_skills": [],
                "missing_skills": [],
                "weak_skills": [],
                "tailored_bullets": [],
                "ats_keywords": [],
                "cover_letter": "Evidence-backed finalization gate cover letter.",
                "cover_letter_evidence_ids": [],
                "interview_questions": [],
                "validation_warnings": [],
                "validation_status": "pass",
                "next_actions": [],
            },
            report_markdown="# PostgreSQL concurrency finalization gate\n",
            validation_warnings_json=[],
            workflow_mode="deterministic_fallback",
        )
        db.add(analysis)
        db.flush()
        analysis.report_json = {**analysis.report_json, "analysis_id": analysis.id}
        usage = UsageEventRecord(
            user_id=user.id,
            event_type="analysis_created",
            quantity=1,
            metadata_json={"status": "reserved"},
            state="reserved",
            reservation_key=f"finalization:{seed_key}",
            reserved_at=datetime.now(UTC),
        )
        db.add(usage)
        db.commit()
        user_id = user.id
        resume_id = resume.id
        job_id = job.id
        analysis_id = analysis.id
        usage_id = usage.id

    request = JobAnalysisRequest(resume_id=resume_id, job_text=job_text)
    current_user = CurrentUser(
        id=user_id,
        external_id=f"finalization-gate-{seed_key}",
        email="finalization-gate@example.com",
        display_name="Finalization Gate",
        plan="premium",
        subscription_status="active",
    )
    barrier = Barrier(2)

    def finalize_replay() -> int:
        with session_factory() as db:
            replay_analysis = db.get(AnalysisRecord, analysis_id)
            replay_resume = db.get(ResumeRecord, resume_id)
            replay_job = db.get(JobRecord, job_id)
            replay_usage = db.get(UsageEventRecord, usage_id)
            if not all((replay_analysis, replay_resume, replay_job, replay_usage)):
                raise AssertionError("Finalization concurrency seed disappeared")
            barrier.wait(timeout=10)
            finalized = finalize_analysis_transaction(
                db,
                request=request,
                current_user=current_user,
                resume=replay_resume,
                job=replay_job,
                analysis=replay_analysis,
                application=None,
                analysis_usage=replay_usage,
            )
            return finalized.id

    with ThreadPoolExecutor(max_workers=2) as executor:
        finalized_ids = list(executor.map(lambda _index: finalize_replay(), range(2)))
    if finalized_ids != [analysis_id, analysis_id]:
        raise AssertionError(f"Concurrent finalization returned unexpected IDs: {finalized_ids}")

    with session_factory() as db:
        application_count = db.scalar(
            sa.select(sa.func.count())
            .select_from(ApplicationRecord)
            .where(
                ApplicationRecord.user_id == user_id,
                ApplicationRecord.report_id == analysis_id,
            )
        )
        if application_count != 1:
            raise AssertionError(
                f"Concurrent finalization created {application_count} applications"
            )
        for event_type in ("application.analyzed", "job.analyzed"):
            audit_count = db.scalar(
                sa.select(sa.func.count())
                .select_from(AuditEventRecord)
                .where(
                    AuditEventRecord.user_id == user_id,
                    AuditEventRecord.event_type == event_type,
                    AuditEventRecord.payload_json["analysis_id"].as_integer() == analysis_id,
                )
            )
            if audit_count != 1:
                raise AssertionError(
                    f"Concurrent finalization created {audit_count} {event_type} events"
                )
        settled_usage = db.get(UsageEventRecord, usage_id)
        if (
            settled_usage is None
            or settled_usage.state != "consumed"
            or settled_usage.settled_at is None
            or settled_usage.metadata_json.get("analysis_id") != analysis_id
        ):
            raise AssertionError("Concurrent finalization did not settle usage exactly once")
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

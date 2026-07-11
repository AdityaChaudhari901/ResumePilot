import json

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config

from app.core.config import get_cached_settings


def test_workflow_provenance_preflight_leaves_sqlite_retryable(tmp_path, monkeypatch):
    database_url = f"sqlite:///{tmp_path / 'provenance-preflight.db'}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("RESUMEPILOT_DATA_DIR", str(tmp_path / "data"))
    get_cached_settings.cache_clear()
    config = Config("alembic.ini")
    engine = sa.create_engine(database_url)

    try:
        command.upgrade(config, "20260710_0010")
        _seed_duplicate_active_application_analyses(engine)

        with pytest.raises(RuntimeError, match="duplicate active operations exist"):
            command.upgrade(config, "head")

        inspector = sa.inspect(engine)
        assert "application_id" not in {
            column["name"] for column in inspector.get_columns("workflow_jobs")
        }
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == (
                "20260710_0010"
            )

        with engine.begin() as connection:
            connection.execute(
                sa.text(
                    "UPDATE workflow_jobs SET status = 'canceled', stage = 'canceled' "
                    "WHERE id = :operation_id"
                ),
                {"operation_id": "00000000-0000-4000-8000-000000000902"},
            )

        command.upgrade(config, "head")

        inspector = sa.inspect(engine)
        assert "application_id" in {
            column["name"] for column in inspector.get_columns("workflow_jobs")
        }
        assert "uq_workflow_jobs_active_analysis_application" in {
            index["name"] for index in inspector.get_indexes("workflow_jobs")
        }
        with engine.connect() as connection:
            assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == (
                "20260711_0011"
            )
    finally:
        engine.dispose()
        get_cached_settings.cache_clear()


def _seed_duplicate_active_application_analyses(engine: sa.Engine) -> None:
    payload = json.dumps({"application_id": 303})
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                """
                INSERT INTO users (
                    id, external_id, email, display_name, plan, stripe_customer_id,
                    subscription_status, created_at, updated_at
                ) VALUES (
                    101, 'migration-user', NULL, 'Migration User', 'free', NULL,
                    'inactive', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            )
        )
        connection.execute(
            sa.text(
                """
                INSERT INTO applications (
                    id, user_id, source_type, source_url, reviewed_job_text,
                    source_content_hash, status, company, role,
                    reviewed_job_profile_json, resume_id, job_id, analysis_id,
                    report_id, match_score, scoring_version, score_status,
                    created_at, updated_at
                ) VALUES (
                    303, 101, 'pasted_text', NULL,
                    'A sufficiently complete reviewed job description for migration testing.',
                    :content_hash, 'reviewed', 'Migration Labs', 'Engineer', :profile,
                    NULL, NULL, NULL, NULL, NULL, NULL, NULL,
                    CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
                """
            ),
            {"content_hash": "a" * 64, "profile": "{}"},
        )
        for index, operation_id in enumerate(
            (
                "00000000-0000-4000-8000-000000000901",
                "00000000-0000-4000-8000-000000000902",
            ),
            start=1,
        ):
            connection.execute(
                sa.text(
                    """
                    INSERT INTO usage_events (
                        id, user_id, event_type, quantity, cost_estimate_usd,
                        metadata_json, state, reservation_key, reserved_at, settled_at,
                        created_at
                    ) VALUES (
                        :usage_id, 101, 'analysis_created', 1, NULL, '{}',
                        'reserved', :operation_id, CURRENT_TIMESTAMP, NULL,
                        CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"usage_id": 400 + index, "operation_id": operation_id},
            )
            connection.execute(
                sa.text(
                    """
                    INSERT INTO workflow_jobs (
                        id, user_id, kind, status, idempotency_key_hash,
                        request_fingerprint, payload_json, scoring_version, stage,
                        progress_percent, attempt_count, max_attempts, priority,
                        available_at, lease_owner, lease_expires_at, heartbeat_at,
                        cancel_requested_at, usage_event_id, analysis_id, result_json,
                        error_code, error_message, request_id, created_at, updated_at,
                        started_at, finished_at
                    ) VALUES (
                        :operation_id, 101, 'analysis', 'queued', :key_hash,
                        :fingerprint, :payload, 'evidence_v2', 'queued', 0, 0, 3, 0,
                        CURRENT_TIMESTAMP, NULL, NULL, NULL, NULL, :usage_id, NULL,
                        '{}', NULL, NULL, NULL, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
                        NULL, NULL
                    )
                    """
                ),
                {
                    "fingerprint": str(index) * 64,
                    "key_hash": str(index + 2) * 64,
                    "operation_id": operation_id,
                    "payload": payload,
                    "usage_id": 400 + index,
                },
            )

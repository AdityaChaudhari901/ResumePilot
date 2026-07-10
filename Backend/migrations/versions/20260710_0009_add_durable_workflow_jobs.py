"""add durable workflow jobs and source snapshots

Revision ID: 20260710_0009
Revises: 20260710_0008
Create Date: 2026-07-10
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0009"
down_revision: str | Sequence[str] | None = "20260710_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    _add_application_source_snapshots()
    _add_usage_reservation_state()
    _create_workflow_jobs()
    _link_analyses_to_workflow_jobs()


def downgrade() -> None:
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.drop_constraint("fk_analyses_workflow_job_id", type_="foreignkey")
        batch_op.drop_constraint("uq_analyses_workflow_job_id", type_="unique")
        batch_op.drop_column("workflow_job_id")

    op.drop_index("ix_workflow_jobs_user_created_id", table_name="workflow_jobs")
    op.drop_index("ix_workflow_jobs_stale_lease", table_name="workflow_jobs")
    op.drop_index("ix_workflow_jobs_claim", table_name="workflow_jobs")
    op.drop_index(op.f("ix_workflow_jobs_analysis_id"), table_name="workflow_jobs")
    op.drop_index(op.f("ix_workflow_jobs_status"), table_name="workflow_jobs")
    op.drop_index(op.f("ix_workflow_jobs_kind"), table_name="workflow_jobs")
    op.drop_index(op.f("ix_workflow_jobs_user_id"), table_name="workflow_jobs")
    op.drop_table("workflow_jobs")

    op.drop_index("ix_usage_events_user_type_state_created", table_name="usage_events")
    op.drop_index(op.f("ix_usage_events_state"), table_name="usage_events")
    with op.batch_alter_table("usage_events") as batch_op:
        batch_op.drop_constraint("uq_usage_events_reservation_key", type_="unique")
        batch_op.drop_column("settled_at")
        batch_op.drop_column("reserved_at")
        batch_op.drop_column("reservation_key")
        batch_op.drop_column("state")

    bind = op.get_bind()
    applications = sa.table(
        "applications",
        sa.column("id", sa.Integer()),
        sa.column("source_url", sa.Text()),
    )
    bind.execute(
        sa.update(applications)
        .where(applications.c.source_url.is_(None))
        .values(source_url=sa.literal("pasted-job-description"))
    )
    op.drop_index(op.f("ix_applications_source_content_hash"), table_name="applications")
    with op.batch_alter_table("applications") as batch_op:
        batch_op.alter_column("source_url", existing_type=sa.Text(), nullable=False)
        batch_op.drop_column("source_content_hash")
        batch_op.drop_column("reviewed_job_text")
        batch_op.drop_column("source_type")


def _add_application_source_snapshots() -> None:
    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("source_type", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("reviewed_job_text", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("source_content_hash", sa.String(length=64), nullable=True))
        batch_op.alter_column("source_url", existing_type=sa.Text(), nullable=True)

    bind = op.get_bind()
    applications = sa.table(
        "applications",
        sa.column("id", sa.Integer()),
        sa.column("source_url", sa.Text()),
        sa.column("job_id", sa.Integer()),
        sa.column("reviewed_job_profile_json", sa.JSON()),
        sa.column("source_type", sa.String()),
        sa.column("reviewed_job_text", sa.Text()),
        sa.column("source_content_hash", sa.String()),
    )
    jobs = sa.table(
        "jobs",
        sa.column("id", sa.Integer()),
        sa.column("raw_text", sa.Text()),
    )
    rows = bind.execute(
        sa.select(
            applications.c.id,
            applications.c.source_url,
            applications.c.reviewed_job_profile_json,
            jobs.c.raw_text,
        ).select_from(applications.outerjoin(jobs, applications.c.job_id == jobs.c.id))
    ).mappings()
    for row in rows:
        reviewed_text = row["raw_text"] or _legacy_profile_snapshot(
            row["reviewed_job_profile_json"]
        )
        source_type = "url" if row["source_url"] else "pasted_text"
        bind.execute(
            sa.update(applications)
            .where(applications.c.id == row["id"])
            .values(
                source_type=source_type,
                reviewed_job_text=reviewed_text,
                source_content_hash=_sha256(reviewed_text),
            )
        )

    with op.batch_alter_table("applications") as batch_op:
        batch_op.alter_column(
            "source_type",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch_op.alter_column("reviewed_job_text", existing_type=sa.Text(), nullable=False)
        batch_op.alter_column(
            "source_content_hash",
            existing_type=sa.String(length=64),
            nullable=False,
        )
    op.create_index(
        op.f("ix_applications_source_content_hash"),
        "applications",
        ["source_content_hash"],
    )


def _add_usage_reservation_state() -> None:
    with op.batch_alter_table("usage_events") as batch_op:
        batch_op.add_column(sa.Column("state", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("reservation_key", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("reserved_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("settled_at", sa.DateTime(), nullable=True))

    bind = op.get_bind()
    usage_events = sa.table(
        "usage_events",
        sa.column("id", sa.Integer()),
        sa.column("metadata_json", sa.JSON()),
        sa.column("created_at", sa.DateTime()),
        sa.column("state", sa.String()),
        sa.column("settled_at", sa.DateTime()),
    )
    rows = bind.execute(
        sa.select(
            usage_events.c.id,
            usage_events.c.metadata_json,
            usage_events.c.created_at,
        )
    ).mappings()
    for row in rows:
        metadata = row["metadata_json"] if isinstance(row["metadata_json"], dict) else {}
        runtime_status = str(metadata.get("status", "completed")).casefold()
        state = (
            "released"
            if runtime_status in {"reserved", "failed", "canceled", "cancelled"}
            else "consumed"
        )
        bind.execute(
            sa.update(usage_events)
            .where(usage_events.c.id == row["id"])
            .values(state=state, settled_at=row["created_at"] or datetime.now(UTC))
        )

    with op.batch_alter_table("usage_events") as batch_op:
        batch_op.alter_column(
            "state",
            existing_type=sa.String(length=32),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_usage_events_reservation_key",
            ["reservation_key"],
        )
    op.create_index(op.f("ix_usage_events_state"), "usage_events", ["state"])
    op.create_index(
        "ix_usage_events_user_type_state_created",
        "usage_events",
        ["user_id", "event_type", "state", "created_at"],
    )


def _create_workflow_jobs() -> None:
    op.create_table(
        "workflow_jobs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("idempotency_key_hash", sa.String(length=64), nullable=False),
        sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False),
        sa.Column("progress_percent", sa.Integer(), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False),
        sa.Column("available_at", sa.DateTime(), nullable=False),
        sa.Column("lease_owner", sa.String(length=255), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(), nullable=True),
        sa.Column("cancel_requested_at", sa.DateTime(), nullable=True),
        sa.Column("usage_event_id", sa.Integer(), nullable=False),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("result_json", sa.JSON(), nullable=False),
        sa.Column("error_code", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.String(length=500), nullable=True),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_workflow_jobs_user_id"),
        sa.ForeignKeyConstraint(
            ["usage_event_id"],
            ["usage_events.id"],
            name="fk_workflow_jobs_usage_event_id",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "kind",
            "idempotency_key_hash",
            name="uq_workflow_jobs_user_kind_idempotency",
        ),
        sa.UniqueConstraint("usage_event_id", name="uq_workflow_jobs_usage_event"),
    )
    op.create_index(op.f("ix_workflow_jobs_user_id"), "workflow_jobs", ["user_id"])
    op.create_index(op.f("ix_workflow_jobs_kind"), "workflow_jobs", ["kind"])
    op.create_index(op.f("ix_workflow_jobs_status"), "workflow_jobs", ["status"])
    op.create_index(op.f("ix_workflow_jobs_analysis_id"), "workflow_jobs", ["analysis_id"])
    op.create_index(
        "ix_workflow_jobs_claim",
        "workflow_jobs",
        ["status", "available_at", "priority", "created_at"],
    )
    op.create_index(
        "ix_workflow_jobs_stale_lease",
        "workflow_jobs",
        ["status", "lease_expires_at"],
    )
    op.create_index(
        "ix_workflow_jobs_user_created_id",
        "workflow_jobs",
        ["user_id", "created_at", "id"],
    )


def _link_analyses_to_workflow_jobs() -> None:
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.add_column(sa.Column("workflow_job_id", sa.String(length=36), nullable=True))
        batch_op.create_unique_constraint(
            "uq_analyses_workflow_job_id",
            ["workflow_job_id"],
        )
        batch_op.create_foreign_key(
            "fk_analyses_workflow_job_id",
            "workflow_jobs",
            ["workflow_job_id"],
            ["id"],
        )


def _legacy_profile_snapshot(profile: Any) -> str:
    value = profile if isinstance(profile, dict) else {}
    rendered = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return rendered if len(rendered) >= 40 else f"Legacy reviewed job profile snapshot: {rendered}"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

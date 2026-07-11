"""add workflow application provenance

Revision ID: 20260711_0011
Revises: 20260710_0010
Create Date: 2026-07-11
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

import sqlalchemy as sa
from alembic import op

revision: str = "20260711_0011"
down_revision: str | Sequence[str] | None = "20260710_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ACTIVE_ANALYSIS_STATUSES = (
    "queued",
    "running",
    "retry_scheduled",
    "cancel_requested",
    "waiting_for_approval",
)
ACTIVE_ANALYSIS_PREDICATE = (
    "kind = 'analysis' AND application_id IS NOT NULL AND status IN "
    "('queued', 'running', 'retry_scheduled', 'cancel_requested', 'waiting_for_approval')"
)


def upgrade() -> None:
    _preflight_duplicate_active_analyses()
    with op.batch_alter_table("workflow_jobs") as batch_op:
        batch_op.add_column(sa.Column("application_id", sa.Integer(), nullable=True))
    _backfill_application_provenance()
    op.create_index(
        "uq_workflow_jobs_active_analysis_application",
        "workflow_jobs",
        ["user_id", "application_id"],
        unique=True,
        postgresql_where=sa.text(ACTIVE_ANALYSIS_PREDICATE),
        sqlite_where=sa.text(ACTIVE_ANALYSIS_PREDICATE),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_workflow_jobs_active_analysis_application",
        table_name="workflow_jobs",
    )
    with op.batch_alter_table("workflow_jobs") as batch_op:
        batch_op.drop_column("application_id")


def _backfill_application_provenance() -> None:
    bind = op.get_bind()
    workflow_jobs = sa.table(
        "workflow_jobs",
        sa.column("id", sa.String()),
        sa.column("user_id", sa.Integer()),
        sa.column("kind", sa.String()),
        sa.column("status", sa.String()),
        sa.column("analysis_id", sa.Integer()),
        sa.column("payload_json", sa.JSON()),
        sa.column("application_id", sa.Integer()),
    )
    application_by_analysis = _application_ids_by_analysis(bind)

    for row in bind.execute(
        sa.select(
            workflow_jobs.c.id,
            workflow_jobs.c.analysis_id,
            workflow_jobs.c.payload_json,
        )
    ).mappings():
        application_id = _workflow_application_id(row, application_by_analysis)
        if application_id is not None:
            bind.execute(
                sa.update(workflow_jobs)
                .where(workflow_jobs.c.id == row["id"])
                .values(application_id=application_id)
            )


def _preflight_duplicate_active_analyses() -> None:
    bind = op.get_bind()
    workflow_jobs = sa.table(
        "workflow_jobs",
        sa.column("id", sa.String()),
        sa.column("user_id", sa.Integer()),
        sa.column("kind", sa.String()),
        sa.column("status", sa.String()),
        sa.column("analysis_id", sa.Integer()),
        sa.column("payload_json", sa.JSON()),
    )
    application_by_analysis = _application_ids_by_analysis(bind)
    active_by_application: dict[tuple[int, int], str] = {}
    rows = bind.execute(
        sa.select(
            workflow_jobs.c.id,
            workflow_jobs.c.user_id,
            workflow_jobs.c.analysis_id,
            workflow_jobs.c.payload_json,
        ).where(
            workflow_jobs.c.kind == "analysis",
            workflow_jobs.c.status.in_(ACTIVE_ANALYSIS_STATUSES),
        )
    ).mappings()
    for row in rows:
        user_id = _positive_integer(row["user_id"])
        application_id = _workflow_application_id(row, application_by_analysis)
        if user_id is None or application_id is None:
            continue
        key = (user_id, application_id)
        existing_operation_id = active_by_application.get(key)
        if existing_operation_id is not None:
            raise RuntimeError(
                "Cannot add active-analysis uniqueness while duplicate active operations exist "
                f"for user {user_id} and application {application_id} "
                f"({existing_operation_id}, {row['id']}); drain or cancel duplicates first"
            )
        active_by_application[key] = str(row["id"])


def _application_ids_by_analysis(bind: Any) -> dict[int, int]:
    applications = sa.table(
        "applications",
        sa.column("id", sa.Integer()),
        sa.column("analysis_id", sa.Integer()),
    )
    application_by_analysis: dict[int, int] = {}
    for row in bind.execute(
        sa.select(applications.c.id, applications.c.analysis_id).where(
            applications.c.analysis_id.is_not(None)
        )
    ).mappings():
        analysis_id = _positive_integer(row["analysis_id"])
        application_id = _positive_integer(row["id"])
        if analysis_id is not None and application_id is not None:
            application_by_analysis.setdefault(analysis_id, application_id)
    return application_by_analysis


def _workflow_application_id(
    row: Mapping[str, Any],
    application_by_analysis: Mapping[int, int],
) -> int | None:
    payload = row["payload_json"]
    payload_application_id = (
        _positive_integer(payload.get("application_id")) if isinstance(payload, Mapping) else None
    )
    analysis_id = _positive_integer(row["analysis_id"])
    return payload_application_id or (
        application_by_analysis.get(analysis_id) if analysis_id is not None else None
    )


def _positive_integer(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value

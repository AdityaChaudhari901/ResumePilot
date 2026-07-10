"""version deterministic match scores

Revision ID: 20260710_0010
Revises: 20260710_0009
Create Date: 2026-07-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0010"
down_revision: str | Sequence[str] | None = "20260710_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_UNVERSIONED = "legacy_unversioned"
DETERMINISTIC_V1 = "deterministic_v1"
SCORED = "scored"
ANALYSIS_ROLLBACK_TABLE = "score_contract_0010_analysis_rollback"
WORKFLOW_ROLLBACK_TABLE = "score_contract_0010_workflow_rollback"
ACTIVE_WORKFLOW_STATUSES = (
    "queued",
    "running",
    "retry_scheduled",
    "cancel_requested",
    "waiting_for_approval",
)


def upgrade() -> None:
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.add_column(
            sa.Column(
                "scoring_version",
                sa.String(length=64),
                nullable=False,
                server_default=LEGACY_UNVERSIONED,
            )
        )
        batch_op.add_column(
            sa.Column(
                "score_status",
                sa.String(length=32),
                nullable=False,
                server_default=SCORED,
            )
        )
        batch_op.add_column(sa.Column("score_breakdown_json", sa.JSON(), nullable=True))

    with op.batch_alter_table("applications") as batch_op:
        batch_op.add_column(sa.Column("scoring_version", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("score_status", sa.String(length=32), nullable=True))

    with op.batch_alter_table("workflow_jobs") as batch_op:
        batch_op.add_column(sa.Column("scoring_version", sa.String(length=64), nullable=True))
        batch_op.create_check_constraint(
            "ck_workflow_jobs_evidence_v2_worker",
            "kind <> 'analysis' OR scoring_version IS NULL OR "
            "scoring_version <> 'evidence_v2' OR status <> 'running' OR "
            "lease_owner LIKE 'score-v2:%'",
        )

    _backfill_score_contracts()
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.alter_column(
            "scoring_version",
            existing_type=sa.String(length=64),
            server_default=DETERMINISTIC_V1,
        )


def downgrade() -> None:
    _lock_score_tables_for_downgrade()
    _reject_active_evidence_v2_workflows()
    _preserve_score_contracts_for_rollback()
    with op.batch_alter_table("workflow_jobs") as batch_op:
        batch_op.drop_constraint("ck_workflow_jobs_evidence_v2_worker", type_="check")
        batch_op.drop_column("scoring_version")
    with op.batch_alter_table("applications") as batch_op:
        batch_op.drop_column("score_status")
        batch_op.drop_column("scoring_version")
    with op.batch_alter_table("analyses") as batch_op:
        batch_op.drop_column("score_breakdown_json")
        batch_op.drop_column("score_status")
        batch_op.drop_column("scoring_version")


def _lock_score_tables_for_downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(
            sa.text("LOCK TABLE workflow_jobs, analyses, applications IN ACCESS EXCLUSIVE MODE")
        )


def _backfill_score_contracts() -> None:
    bind = op.get_bind()
    analyses = sa.table(
        "analyses",
        sa.column("id", sa.Integer()),
        sa.column("workflow_job_id", sa.String()),
        sa.column("scoring_version", sa.String()),
        sa.column("score_status", sa.String()),
        sa.column("score_breakdown_json", sa.JSON()),
    )
    applications = sa.table(
        "applications",
        sa.column("analysis_id", sa.Integer()),
        sa.column("match_score", sa.Float()),
        sa.column("scoring_version", sa.String()),
        sa.column("score_status", sa.String()),
    )
    workflow_jobs = sa.table(
        "workflow_jobs",
        sa.column("id", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("analysis_id", sa.Integer()),
        sa.column("scoring_version", sa.String()),
    )

    bind.execute(
        sa.update(analyses)
        .where(analyses.c.workflow_job_id.is_not(None))
        .values(scoring_version=DETERMINISTIC_V1)
    )

    _restore_analysis_score_contracts(bind, analyses)

    linked_analysis_version = (
        sa.select(analyses.c.scoring_version)
        .where(analyses.c.id == applications.c.analysis_id)
        .scalar_subquery()
    )
    linked_analysis_status = (
        sa.select(analyses.c.score_status)
        .where(analyses.c.id == applications.c.analysis_id)
        .scalar_subquery()
    )
    bind.execute(
        sa.update(applications)
        .where(applications.c.match_score.is_not(None))
        .values(
            scoring_version=sa.func.coalesce(
                linked_analysis_version,
                LEGACY_UNVERSIONED,
            ),
            score_status=sa.func.coalesce(linked_analysis_status, SCORED),
        )
    )

    linked_workflow_analysis_version = (
        sa.select(analyses.c.scoring_version)
        .where(analyses.c.id == workflow_jobs.c.analysis_id)
        .scalar_subquery()
    )
    bind.execute(
        sa.update(workflow_jobs)
        .where(workflow_jobs.c.kind == "analysis")
        .values(
            scoring_version=sa.func.coalesce(
                linked_workflow_analysis_version,
                DETERMINISTIC_V1,
            )
        )
    )
    _restore_queued_workflow_versions(bind, workflow_jobs)
    _drop_rollback_tables_if_present(bind)


def _preserve_score_contracts_for_rollback() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table_name in (ANALYSIS_ROLLBACK_TABLE, WORKFLOW_ROLLBACK_TABLE):
        if inspector.has_table(table_name):
            raise RuntimeError(f"Rollback preservation table already exists: {table_name}")

    analysis_backup = op.create_table(
        ANALYSIS_ROLLBACK_TABLE,
        sa.Column(
            "analysis_id",
            sa.Integer(),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("workflow_job_id", sa.String(length=36), nullable=True),
        sa.Column("scoring_version", sa.String(length=64), nullable=False),
        sa.Column("score_status", sa.String(length=32), nullable=False),
        sa.Column("score_breakdown_json", sa.JSON(), nullable=True),
    )
    workflow_backup = op.create_table(
        WORKFLOW_ROLLBACK_TABLE,
        sa.Column(
            "workflow_job_id",
            sa.String(length=36),
            sa.ForeignKey("workflow_jobs.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("scoring_version", sa.String(length=64), nullable=False),
    )
    analyses = sa.table(
        "analyses",
        sa.column("id", sa.Integer()),
        sa.column("workflow_job_id", sa.String()),
        sa.column("scoring_version", sa.String()),
        sa.column("score_status", sa.String()),
        sa.column("score_breakdown_json", sa.JSON()),
    )
    workflow_jobs = sa.table(
        "workflow_jobs",
        sa.column("id", sa.String()),
        sa.column("kind", sa.String()),
        sa.column("analysis_id", sa.Integer()),
        sa.column("scoring_version", sa.String()),
    )
    bind.execute(
        sa.insert(analysis_backup).from_select(
            [
                "analysis_id",
                "workflow_job_id",
                "scoring_version",
                "score_status",
                "score_breakdown_json",
            ],
            sa.select(
                analyses.c.id,
                analyses.c.workflow_job_id,
                analyses.c.scoring_version,
                analyses.c.score_status,
                analyses.c.score_breakdown_json,
            ),
        )
    )
    bind.execute(
        sa.insert(workflow_backup).from_select(
            ["workflow_job_id", "scoring_version"],
            sa.select(workflow_jobs.c.id, workflow_jobs.c.scoring_version).where(
                workflow_jobs.c.kind == "analysis",
                workflow_jobs.c.analysis_id.is_(None),
                workflow_jobs.c.scoring_version.is_not(None),
            ),
        )
    )


def _reject_active_evidence_v2_workflows() -> None:
    bind = op.get_bind()
    workflow_jobs = sa.table(
        "workflow_jobs",
        sa.column("kind", sa.String()),
        sa.column("status", sa.String()),
        sa.column("scoring_version", sa.String()),
    )
    active_count = bind.scalar(
        sa.select(sa.func.count())
        .select_from(workflow_jobs)
        .where(
            workflow_jobs.c.kind == "analysis",
            workflow_jobs.c.scoring_version == "evidence_v2",
            workflow_jobs.c.status.in_(ACTIVE_WORKFLOW_STATUSES),
        )
    )
    if active_count:
        raise RuntimeError(
            "Cannot downgrade score versioning while evidence_v2 analysis workflows are active; "
            "drain or cancel them before rollback"
        )


def _restore_analysis_score_contracts(bind, analyses) -> None:
    if not sa.inspect(bind).has_table(ANALYSIS_ROLLBACK_TABLE):
        return
    backup = sa.table(
        ANALYSIS_ROLLBACK_TABLE,
        sa.column("analysis_id", sa.Integer()),
        sa.column("workflow_job_id", sa.String()),
        sa.column("scoring_version", sa.String()),
        sa.column("score_status", sa.String()),
        sa.column("score_breakdown_json", sa.JSON()),
    )
    unchanged_workflow = sa.or_(
        backup.c.workflow_job_id == analyses.c.workflow_job_id,
        sa.and_(
            backup.c.workflow_job_id.is_(None),
            analyses.c.workflow_job_id.is_(None),
        ),
    )
    matching_backup = sa.and_(
        backup.c.analysis_id == analyses.c.id,
        unchanged_workflow,
    )
    bind.execute(
        sa.update(analyses)
        .where(sa.exists(sa.select(1).select_from(backup).where(matching_backup)))
        .values(
            scoring_version=sa.select(backup.c.scoring_version)
            .where(matching_backup)
            .scalar_subquery(),
            score_status=sa.select(backup.c.score_status).where(matching_backup).scalar_subquery(),
            score_breakdown_json=sa.select(backup.c.score_breakdown_json)
            .where(matching_backup)
            .scalar_subquery(),
        )
    )


def _restore_queued_workflow_versions(bind, workflow_jobs) -> None:
    if not sa.inspect(bind).has_table(WORKFLOW_ROLLBACK_TABLE):
        return
    backup = sa.table(
        WORKFLOW_ROLLBACK_TABLE,
        sa.column("workflow_job_id", sa.String()),
        sa.column("scoring_version", sa.String()),
    )
    matching_backup = backup.c.workflow_job_id == workflow_jobs.c.id
    bind.execute(
        sa.update(workflow_jobs)
        .where(
            workflow_jobs.c.kind == "analysis",
            workflow_jobs.c.analysis_id.is_(None),
            sa.exists(sa.select(1).select_from(backup).where(matching_backup)),
        )
        .values(
            scoring_version=sa.select(backup.c.scoring_version)
            .where(matching_backup)
            .scalar_subquery()
        )
    )


def _drop_rollback_tables_if_present(bind) -> None:
    inspector = sa.inspect(bind)
    if inspector.has_table(WORKFLOW_ROLLBACK_TABLE):
        op.drop_table(WORKFLOW_ROLLBACK_TABLE)
    if inspector.has_table(ANALYSIS_ROLLBACK_TABLE):
        op.drop_table(ANALYSIS_ROLLBACK_TABLE)

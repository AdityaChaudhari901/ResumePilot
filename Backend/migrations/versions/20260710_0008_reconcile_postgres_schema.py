"""reconcile tenant constraints and history indexes

Revision ID: 20260710_0008
Revises: 20260709_0007
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260710_0008"
down_revision: str | Sequence[str] | None = "20260709_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

OWNERSHIP_FOREIGN_KEYS = (
    ("resumes", "fk_resumes_user_id_users"),
    ("jobs", "fk_jobs_user_id_users"),
    ("analyses", "fk_analyses_user_id_users"),
    ("audit_events", "fk_audit_events_user_id_users"),
)
HISTORY_INDEXES = (
    ("ix_analyses_user_created_id", "analyses", ("user_id", "created_at", "id")),
    (
        "ix_applications_user_updated_id",
        "applications",
        ("user_id", "updated_at", "id"),
    ),
    (
        "ix_applications_user_status_updated_id",
        "applications",
        ("user_id", "status", "updated_at", "id"),
    ),
    ("ix_audit_events_user_created_id", "audit_events", ("user_id", "created_at", "id")),
    (
        "ix_audit_events_user_event_created_id",
        "audit_events",
        ("user_id", "event_type", "created_at", "id"),
    ),
)
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


def upgrade() -> None:
    bind = op.get_bind()
    _validate_ownership_data(bind)
    _validate_resume_uniqueness(bind)

    if bind.dialect.name == "sqlite":
        _upgrade_sqlite_constraints()
    else:
        _upgrade_standard_constraints()

    for index_name, table_name, columns in HISTORY_INDEXES:
        op.create_index(index_name, table_name, list(columns))

    if bind.dialect.name == "postgresql":
        _advance_postgresql_sequences(bind)


def downgrade() -> None:
    bind = op.get_bind()

    for index_name, table_name, _columns in reversed(HISTORY_INDEXES):
        op.drop_index(index_name, table_name=table_name)

    if bind.dialect.name == "sqlite":
        _downgrade_sqlite_constraints()
    else:
        _downgrade_standard_constraints()

    # PostgreSQL sequences intentionally remain monotonic. Lowering a sequence during
    # rollback can reissue an identifier that was allocated after this migration ran.


def _upgrade_standard_constraints() -> None:
    for table_name, constraint_name in OWNERSHIP_FOREIGN_KEYS:
        op.create_foreign_key(
            constraint_name,
            table_name,
            "users",
            ["user_id"],
            ["id"],
        )

    if op.get_bind().dialect.name == "postgresql":
        # Reuse the existing unique index so PostgreSQL does not rebuild and re-scan it.
        op.execute(
            'ALTER TABLE "resumes" ADD CONSTRAINT "uq_resumes_user_file_hash" '
            'UNIQUE USING INDEX "uq_resumes_user_file_hash"'
        )
    else:
        op.drop_index("uq_resumes_user_file_hash", table_name="resumes")
        op.create_unique_constraint(
            "uq_resumes_user_file_hash",
            "resumes",
            ["user_id", "file_hash"],
        )


def _downgrade_standard_constraints() -> None:
    op.drop_constraint("uq_resumes_user_file_hash", "resumes", type_="unique")
    op.create_index(
        "uq_resumes_user_file_hash",
        "resumes",
        ["user_id", "file_hash"],
        unique=True,
    )
    for table_name, constraint_name in reversed(OWNERSHIP_FOREIGN_KEYS):
        op.drop_constraint(constraint_name, table_name, type_="foreignkey")


def _upgrade_sqlite_constraints() -> None:
    with op.batch_alter_table("resumes", recreate="always") as batch_op:
        batch_op.drop_index("uq_resumes_user_file_hash")
        batch_op.create_unique_constraint(
            "uq_resumes_user_file_hash",
            ["user_id", "file_hash"],
        )
        batch_op.create_foreign_key(
            "fk_resumes_user_id_users",
            "users",
            ["user_id"],
            ["id"],
        )

    for table_name, constraint_name in OWNERSHIP_FOREIGN_KEYS[1:]:
        with op.batch_alter_table(table_name, recreate="always") as batch_op:
            batch_op.create_foreign_key(
                constraint_name,
                "users",
                ["user_id"],
                ["id"],
            )


def _downgrade_sqlite_constraints() -> None:
    for table_name, constraint_name in reversed(OWNERSHIP_FOREIGN_KEYS[1:]):
        with op.batch_alter_table(table_name, recreate="always") as batch_op:
            batch_op.drop_constraint(constraint_name, type_="foreignkey")

    with op.batch_alter_table("resumes", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_resumes_user_id_users", type_="foreignkey")
        batch_op.drop_constraint("uq_resumes_user_file_hash", type_="unique")
        batch_op.create_index(
            "uq_resumes_user_file_hash",
            ["user_id", "file_hash"],
            unique=True,
        )


def _validate_ownership_data(bind: sa.Connection) -> None:
    users = sa.table("users", sa.column("id", sa.Integer()))
    for table_name, _constraint_name in OWNERSHIP_FOREIGN_KEYS:
        child = sa.table(
            table_name,
            sa.column("user_id", sa.Integer()),
        )
        orphan_count = bind.scalar(
            sa.select(sa.func.count())
            .select_from(child.outerjoin(users, child.c.user_id == users.c.id))
            .where(child.c.user_id.is_not(None), users.c.id.is_(None))
        )
        if orphan_count:
            raise RuntimeError(
                f"Cannot add {table_name}.user_id ownership constraint: "
                f"found {orphan_count} orphaned row(s)."
            )


def _validate_resume_uniqueness(bind: sa.Connection) -> None:
    resumes = sa.table(
        "resumes",
        sa.column("user_id", sa.Integer()),
        sa.column("file_hash", sa.String()),
    )
    duplicate_groups = (
        sa.select(resumes.c.user_id, resumes.c.file_hash)
        .group_by(resumes.c.user_id, resumes.c.file_hash)
        .having(sa.func.count() > 1)
        .subquery()
    )
    duplicate_count = bind.scalar(sa.select(sa.func.count()).select_from(duplicate_groups))
    if duplicate_count:
        raise RuntimeError(
            "Cannot create uq_resumes_user_file_hash: "
            f"found {duplicate_count} duplicate user/file-hash group(s)."
        )


def _advance_postgresql_sequences(bind: sa.Connection) -> None:
    preparer = bind.dialect.identifier_preparer
    for table_name in SEQUENCE_TABLES:
        quoted_table = preparer.quote(table_name)
        bind.execute(
            sa.text(
                "SELECT setval("
                "pg_get_serial_sequence(:table_name, 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {quoted_table}), 1), "
                f"EXISTS(SELECT 1 FROM {quoted_table})"
                ")"
            ),
            {"table_name": table_name},
        )

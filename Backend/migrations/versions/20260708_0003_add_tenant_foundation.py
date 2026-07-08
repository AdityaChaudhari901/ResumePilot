"""add tenant ownership foundation

Revision ID: 20260708_0003
Revises: 20260708_0002
Create Date: 2026-07-08
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0003"
down_revision: str | Sequence[str] | None = "20260708_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_USER_ID = 1


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("plan", sa.String(length=64), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("subscription_status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_id"), "users", ["id"])
    op.create_index(op.f("ix_users_external_id"), "users", ["external_id"], unique=True)
    op.create_index(op.f("ix_users_stripe_customer_id"), "users", ["stripe_customer_id"])

    now = datetime.now(UTC).replace(tzinfo=None)
    users_table = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("external_id", sa.String()),
        sa.column("email", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("plan", sa.String()),
        sa.column("stripe_customer_id", sa.String()),
        sa.column("subscription_status", sa.String()),
        sa.column("created_at", sa.DateTime()),
        sa.column("updated_at", sa.DateTime()),
    )
    op.bulk_insert(
        users_table,
        [
            {
                "id": DEFAULT_USER_ID,
                "external_id": "local-dev-user",
                "email": None,
                "display_name": "Local Developer",
                "plan": "free",
                "stripe_customer_id": None,
                "subscription_status": "inactive",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )

    _add_user_id_column("resumes", nullable=False)
    _add_user_id_column("jobs", nullable=False)
    _add_user_id_column("analyses", nullable=False)
    _add_user_id_column("audit_events", nullable=True)

    op.drop_index(op.f("ix_resumes_file_hash"), table_name="resumes")
    op.create_index(op.f("ix_resumes_file_hash"), "resumes", ["file_hash"])
    op.create_index(op.f("ix_resumes_user_id"), "resumes", ["user_id"])
    op.create_index(
        "uq_resumes_user_file_hash", "resumes", ["user_id", "file_hash"], unique=True
    )
    op.create_index(op.f("ix_jobs_user_id"), "jobs", ["user_id"])
    op.create_index("ix_jobs_user_content_hash", "jobs", ["user_id", "content_hash"])
    op.create_index(op.f("ix_analyses_user_id"), "analyses", ["user_id"])
    op.create_index(op.f("ix_audit_events_user_id"), "audit_events", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_audit_events_user_id"), table_name="audit_events")
    op.drop_index(op.f("ix_analyses_user_id"), table_name="analyses")
    op.drop_index("ix_jobs_user_content_hash", table_name="jobs")
    op.drop_index(op.f("ix_jobs_user_id"), table_name="jobs")
    op.drop_index("uq_resumes_user_file_hash", table_name="resumes")
    op.drop_index(op.f("ix_resumes_user_id"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_file_hash"), table_name="resumes")
    op.create_index(op.f("ix_resumes_file_hash"), "resumes", ["file_hash"], unique=True)

    _drop_user_id_column("audit_events")
    _drop_user_id_column("analyses")
    _drop_user_id_column("jobs")
    _drop_user_id_column("resumes")

    op.drop_index(op.f("ix_users_stripe_customer_id"), table_name="users")
    op.drop_index(op.f("ix_users_external_id"), table_name="users")
    op.drop_index(op.f("ix_users_id"), table_name="users")
    op.drop_table("users")


def _add_user_id_column(table_name: str, *, nullable: bool) -> None:
    op.add_column(table_name, sa.Column("user_id", sa.Integer(), nullable=True))
    op.execute(f"UPDATE {table_name} SET user_id = {DEFAULT_USER_ID} WHERE user_id IS NULL")
    if not nullable:
        with op.batch_alter_table(table_name) as batch_op:
            batch_op.alter_column("user_id", nullable=False, existing_type=sa.Integer())


def _drop_user_id_column(table_name: str) -> None:
    op.drop_column(table_name, "user_id")

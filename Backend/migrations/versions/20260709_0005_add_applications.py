"""add application workspace records

Revision ID: 20260709_0005
Revises: 20260708_0004
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0005"
down_revision: str | Sequence[str] | None = "20260708_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("reviewed_job_profile_json", sa.JSON(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=True),
        sa.Column("job_id", sa.Integer(), nullable=True),
        sa.Column("analysis_id", sa.Integer(), nullable=True),
        sa.Column("report_id", sa.Integer(), nullable=True),
        sa.Column("match_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_applications_id"), "applications", ["id"])
    op.create_index(op.f("ix_applications_user_id"), "applications", ["user_id"])
    op.create_index(op.f("ix_applications_status"), "applications", ["status"])
    op.create_index(op.f("ix_applications_resume_id"), "applications", ["resume_id"])
    op.create_index(op.f("ix_applications_job_id"), "applications", ["job_id"])
    op.create_index(op.f("ix_applications_analysis_id"), "applications", ["analysis_id"])
    op.create_index(op.f("ix_applications_report_id"), "applications", ["report_id"])
    op.create_index(
        "ix_applications_user_status_created",
        "applications",
        ["user_id", "status", "created_at"],
    )
    op.create_index("ix_applications_user_report", "applications", ["user_id", "report_id"])


def downgrade() -> None:
    op.drop_index("ix_applications_user_report", table_name="applications")
    op.drop_index("ix_applications_user_status_created", table_name="applications")
    op.drop_index(op.f("ix_applications_report_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_analysis_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_job_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_resume_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_status"), table_name="applications")
    op.drop_index(op.f("ix_applications_user_id"), table_name="applications")
    op.drop_index(op.f("ix_applications_id"), table_name="applications")
    op.drop_table("applications")

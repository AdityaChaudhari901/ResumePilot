"""initial schema

Revision ID: 20260708_0001
Revises:
Create Date: 2026-07-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(length=128), nullable=False),
        sa.Column("request_id", sa.String(length=128), nullable=True),
        sa.Column("payload_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_events_event_type"), "audit_events", ["event_type"])
    op.create_index(op.f("ix_audit_events_id"), "audit_events", ["id"])

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("role", sa.String(length=255), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_jobs_content_hash"), "jobs", ["content_hash"])
    op.create_index(op.f("ix_jobs_id"), "jobs", ["id"])

    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_extension", sa.String(length=32), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("profile_json", sa.JSON(), nullable=False),
        sa.Column("candidate_name", sa.String(length=255), nullable=True),
        sa.Column("candidate_email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_resumes_file_hash"), "resumes", ["file_hash"], unique=True)
    op.create_index(op.f("ix_resumes_id"), "resumes", ["id"])

    op.create_table(
        "analyses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("resume_id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("match_score", sa.Float(), nullable=False),
        sa.Column("match_result_json", sa.JSON(), nullable=False),
        sa.Column("report_json", sa.JSON(), nullable=False),
        sa.Column("report_markdown", sa.Text(), nullable=False),
        sa.Column("validation_warnings_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["resume_id"], ["resumes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_analyses_id"), "analyses", ["id"])
    op.create_index(op.f("ix_analyses_job_id"), "analyses", ["job_id"])
    op.create_index(op.f("ix_analyses_resume_id"), "analyses", ["resume_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_analyses_resume_id"), table_name="analyses")
    op.drop_index(op.f("ix_analyses_job_id"), table_name="analyses")
    op.drop_index(op.f("ix_analyses_id"), table_name="analyses")
    op.drop_table("analyses")
    op.drop_index(op.f("ix_resumes_id"), table_name="resumes")
    op.drop_index(op.f("ix_resumes_file_hash"), table_name="resumes")
    op.drop_table("resumes")
    op.drop_index(op.f("ix_jobs_id"), table_name="jobs")
    op.drop_index(op.f("ix_jobs_content_hash"), table_name="jobs")
    op.drop_table("jobs")
    op.drop_index(op.f("ix_audit_events_id"), table_name="audit_events")
    op.drop_index(op.f("ix_audit_events_event_type"), table_name="audit_events")
    op.drop_table("audit_events")

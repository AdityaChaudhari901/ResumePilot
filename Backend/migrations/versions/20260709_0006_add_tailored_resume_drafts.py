"""add tailored resume draft workspace

Revision ID: 20260709_0006
Revises: 20260709_0005
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0006"
down_revision: str | Sequence[str] | None = "20260709_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tailored_resume_drafts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("application_id", sa.Integer(), nullable=False),
        sa.Column("report_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("items_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["application_id"], ["applications.id"]),
        sa.ForeignKeyConstraint(["report_id"], ["analyses.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "report_id", name="uq_tailored_resume_user_report"),
    )
    op.create_index(op.f("ix_tailored_resume_drafts_id"), "tailored_resume_drafts", ["id"])
    op.create_index(
        op.f("ix_tailored_resume_drafts_user_id"),
        "tailored_resume_drafts",
        ["user_id"],
    )
    op.create_index(
        op.f("ix_tailored_resume_drafts_application_id"),
        "tailored_resume_drafts",
        ["application_id"],
    )
    op.create_index(
        op.f("ix_tailored_resume_drafts_report_id"),
        "tailored_resume_drafts",
        ["report_id"],
    )
    op.create_index(
        op.f("ix_tailored_resume_drafts_status"),
        "tailored_resume_drafts",
        ["status"],
    )
    op.create_index(
        "ix_tailored_resume_user_application",
        "tailored_resume_drafts",
        ["user_id", "application_id"],
    )
    op.create_index(
        "ix_tailored_resume_user_report",
        "tailored_resume_drafts",
        ["user_id", "report_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_tailored_resume_user_report", table_name="tailored_resume_drafts")
    op.drop_index("ix_tailored_resume_user_application", table_name="tailored_resume_drafts")
    op.drop_index(op.f("ix_tailored_resume_drafts_status"), table_name="tailored_resume_drafts")
    op.drop_index(
        op.f("ix_tailored_resume_drafts_report_id"),
        table_name="tailored_resume_drafts",
    )
    op.drop_index(
        op.f("ix_tailored_resume_drafts_application_id"),
        table_name="tailored_resume_drafts",
    )
    op.drop_index(
        op.f("ix_tailored_resume_drafts_user_id"),
        table_name="tailored_resume_drafts",
    )
    op.drop_index(op.f("ix_tailored_resume_drafts_id"), table_name="tailored_resume_drafts")
    op.drop_table("tailored_resume_drafts")

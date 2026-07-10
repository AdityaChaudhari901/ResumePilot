"""fix tailored resume draft lifecycle

Revision ID: 20260709_0007
Revises: 20260709_0006
Create Date: 2026-07-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260709_0007"
down_revision: str | Sequence[str] | None = "20260709_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None
DELETE_BATCH_SIZE = 500

tailored_resume_drafts = sa.table(
    "tailored_resume_drafts",
    sa.column("id", sa.Integer()),
    sa.column("user_id", sa.Integer()),
    sa.column("application_id", sa.Integer()),
    sa.column("report_id", sa.Integer()),
)
applications = sa.table(
    "applications",
    sa.column("id", sa.Integer()),
    sa.column("user_id", sa.Integer()),
    sa.column("report_id", sa.Integer()),
)


def upgrade() -> None:
    _delete_drafts_not_linked_to_the_current_application_report()
    op.drop_index("ix_tailored_resume_user_application", table_name="tailored_resume_drafts")
    with op.batch_alter_table("tailored_resume_drafts") as batch_op:
        batch_op.drop_constraint("uq_tailored_resume_user_report", type_="unique")
        batch_op.create_unique_constraint(
            "uq_tailored_resume_user_application",
            ["user_id", "application_id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("tailored_resume_drafts") as batch_op:
        batch_op.drop_constraint("uq_tailored_resume_user_application", type_="unique")
        batch_op.create_unique_constraint(
            "uq_tailored_resume_user_report",
            ["user_id", "report_id"],
        )
    op.create_index(
        "ix_tailored_resume_user_application",
        "tailored_resume_drafts",
        ["user_id", "application_id"],
    )


def _delete_drafts_not_linked_to_the_current_application_report() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.select(
            tailored_resume_drafts.c.id,
            tailored_resume_drafts.c.user_id,
            tailored_resume_drafts.c.report_id,
            applications.c.user_id.label("application_user_id"),
            applications.c.report_id.label("application_report_id"),
        ).select_from(
            tailored_resume_drafts.outerjoin(
                applications,
                tailored_resume_drafts.c.application_id == applications.c.id,
            )
        )
    ).mappings()
    stale_draft_ids = [
        row["id"]
        for row in rows
        if row["application_user_id"] != row["user_id"]
        or row["application_report_id"] != row["report_id"]
    ]
    for start in range(0, len(stale_draft_ids), DELETE_BATCH_SIZE):
        stale_draft_id_batch = stale_draft_ids[start : start + DELETE_BATCH_SIZE]
        bind.execute(
            sa.delete(tailored_resume_drafts).where(
                tailored_resume_drafts.c.id.in_(stale_draft_id_batch)
            )
        )

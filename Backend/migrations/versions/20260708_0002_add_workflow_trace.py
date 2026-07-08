"""add workflow trace metadata

Revision ID: 20260708_0002
Revises: 20260708_0001
Create Date: 2026-07-08
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260708_0002"
down_revision: str | Sequence[str] | None = "20260708_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

DEFAULT_WORKFLOW_TRACE_JSON = (
    '{"mode":"deterministic_fallback","steps":[{"name":"validation_gate",'
    '"status":"degraded","summary":"Workflow trace was not captured for this analysis."}],'
    '"validation_warning_codes":[]}'
)


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column(
            "workflow_mode",
            sa.String(length=64),
            nullable=False,
            server_default="deterministic_fallback",
        ),
    )
    op.add_column(
        "analyses",
        sa.Column(
            "workflow_trace_json",
            sa.JSON(),
            nullable=False,
            server_default=DEFAULT_WORKFLOW_TRACE_JSON,
        ),
    )


def downgrade() -> None:
    op.drop_column("analyses", "workflow_trace_json")
    op.drop_column("analyses", "workflow_mode")

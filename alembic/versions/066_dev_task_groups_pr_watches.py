"""066 — dev_task_groups and pr_watches: teams, arena races, the PR feedback loop.

Spec docs/specs/agent-drivers.md, "Phase 4b (2026-11-27)". ``dev_task_groups``
holds one row per parallel plan (``kind = team``) or arena race (``kind =
arena``); the tasks stay ordinary ``agent_tasks`` rows (dependencies, hand-off
and team membership live in their ``properties``). ``pr_watches`` is the PR
feedback loop's persisted state per task: rounds used and the dedupe keys of
feedback already handed back, so a restart never sends the same comment twice.

Revises 065 (dev automation): both were built in parallel and chained here on
race/migration so there is a single head.

No schema qualifier, matching every migration since 023.

Revision ID: 066
Revises: 065
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "066"
down_revision = "065"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dev_task_groups",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("title", sa.String(200), nullable=False, server_default=""),
        sa.Column("source_ref", sa.String(64), nullable=True),
        sa.Column("properties", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_dev_task_groups_state", "dev_task_groups", ["tenant_id", "kind", "status"])

    op.create_table(
        "pr_watches",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pr_url", sa.String(300), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="watching"),
        sa.Column("rounds", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("seen", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_feedback", sa.String(300), nullable=True),
        sa.Column("last_error", sa.String(300), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("properties", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("tenant_id", "task_id", name="uq_pr_watches_task"),
    )
    op.create_index("ix_pr_watches_state", "pr_watches", ["state"])


def downgrade() -> None:
    op.drop_index("ix_pr_watches_state", table_name="pr_watches")
    op.drop_table("pr_watches")
    op.drop_index("ix_dev_task_groups_state", table_name="dev_task_groups")
    op.drop_table("dev_task_groups")

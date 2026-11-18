"""060 — dev_task_events: the live session log of a dev task.

Work order docs/work-orders/secure-execution-runtime.md, Stage 4. Each row is
one event of a running (or finished) dev task: runner lifecycle, dispatcher
stages, the agent's steps as they stream, verifier verdicts, runtime
start/teardown. ``seq`` is per task and unique, so a viewer reads "everything
after N" and a reconnect resumes without gaps or repeats. Content is redacted
and capped before it is written (services/dev/task_events.py). Rows go with
their task (ON DELETE CASCADE) and are expired after a retention window.

No schema qualifier, matching every migration since 023.

Revision ID: 060
Revises: 059
Create Date: 2026-11-18
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "060"
down_revision = "059"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dev_task_events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("source", sa.String(32), nullable=False, server_default="runner"),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("data", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("task_id", "seq", name="uq_dev_task_events_task_seq"),
    )
    op.create_index(
        "ix_dev_task_events_tenant_task_seq", "dev_task_events", ["tenant_id", "task_id", "seq"]
    )
    op.create_index("ix_dev_task_events_created", "dev_task_events", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_dev_task_events_created", table_name="dev_task_events")
    op.drop_index("ix_dev_task_events_tenant_task_seq", table_name="dev_task_events")
    op.drop_table("dev_task_events")

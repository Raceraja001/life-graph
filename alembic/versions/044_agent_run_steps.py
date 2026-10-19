"""044 — agent_run_steps: every step of a dev-agent driver run.

One row per step (what the agent said, each tool call and its result), per
attempt, so a run can be replayed in order and studied afterwards. Written
from the ``driver:steps`` event by services/trajectories.py; content is
redacted and size-capped before it lands here. Deleted with its task.

No schema qualifier, matching every migration since 023.

Revision ID: 044
Revises: 043
Create Date: 2026-10-13
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "044"
down_revision = "043"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_run_steps",
        sa.Column("id", UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "task_id",
            UUID(),
            sa.ForeignKey("agent_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("driver", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("tool", sa.String(128), nullable=True),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("properties", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("step_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_agent_run_steps_task", "agent_run_steps", ["tenant_id", "task_id", "attempt", "seq"]
    )


def downgrade() -> None:
    op.drop_index("ix_agent_run_steps_task", table_name="agent_run_steps")
    op.drop_table("agent_run_steps")

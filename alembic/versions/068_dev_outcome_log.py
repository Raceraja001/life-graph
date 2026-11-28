"""068 — dev_outcome_log: per-dispatch driver, model, rung, verdicts and outcome.

Spec docs/specs/agent-drivers.md, "Escalation ladder, starting floor, outcome
log (2026-11-28)". One row per dispatch of a dev task: where it started on the
escalation ladder and why, each escalation, rounds, verification and reviewer
verdicts ("not reviewed" included), the final outcome, the owner's decision
once known, duration, cost, and the tier a future rules router would have
picked (shadow only). ``task_id`` is a string with no foreign key: throwaway
dispatch ids are logged too.

No schema qualifier, matching every migration since 023.

Revision ID: 068
Revises: 067
Create Date: 2026-11-28
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "068"
down_revision = "067"
branch_labels = None
depends_on = None


def _json_list() -> sa.TextClause:
    return sa.text("'[]'::jsonb")


def upgrade() -> None:
    op.create_table(
        "dev_outcome_log",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("task_id", sa.String(64), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=True),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("task_type", sa.String(30), nullable=False, server_default="general"),
        sa.Column("persona", sa.String(100), nullable=True),
        sa.Column("instruction_sha", sa.String(64), nullable=False, server_default=""),
        sa.Column("start_driver", sa.String(64), nullable=True),
        sa.Column("start_model", sa.String(120), nullable=True),
        sa.Column("start_tier", sa.String(16), nullable=True),
        sa.Column("start_reason", sa.String(300), nullable=False, server_default=""),
        sa.Column("final_driver", sa.String(64), nullable=True),
        sa.Column("final_model", sa.String(120), nullable=True),
        sa.Column("final_tier", sa.String(16), nullable=True),
        sa.Column("escalations", JSONB(), nullable=False, server_default=_json_list()),
        sa.Column("reached_top", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rounds_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verification", sa.String(16), nullable=False, server_default="not_run"),
        sa.Column("reviews", JSONB(), nullable=False, server_default=_json_list()),
        sa.Column("review_verdict", sa.String(16), nullable=False, server_default="not_reviewed"),
        sa.Column("outcome", sa.String(24), nullable=False),
        sa.Column("owner_decision", sa.String(24), nullable=True),
        sa.Column("owner_decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("shadow_tier", sa.String(16), nullable=True),
        sa.Column("shadow_reasons", JSONB(), nullable=False, server_default=_json_list()),
        sa.Column("error", sa.String(300), nullable=True),
        sa.Column("properties", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "ix_dev_outcome_log_tenant_created", "dev_outcome_log", ["tenant_id", "created_at"]
    )
    op.create_index("ix_dev_outcome_log_task", "dev_outcome_log", ["tenant_id", "task_id"])
    op.create_index(
        "ix_dev_outcome_log_instruction",
        "dev_outcome_log",
        ["tenant_id", "project_id", "instruction_sha"],
    )


def downgrade() -> None:
    op.drop_index("ix_dev_outcome_log_instruction", table_name="dev_outcome_log")
    op.drop_index("ix_dev_outcome_log_task", table_name="dev_outcome_log")
    op.drop_index("ix_dev_outcome_log_tenant_created", table_name="dev_outcome_log")
    op.drop_table("dev_outcome_log")

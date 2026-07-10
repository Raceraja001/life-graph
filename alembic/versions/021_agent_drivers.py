"""021 — Agent Drivers: driver_stats, verification_runs, agent_personas columns.

Revision ID: 021
Revises: 020
Create Date: 2026-07-08
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "021"
down_revision = "020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── driver_stats ─────────────────────────────────────────
    op.create_table(
        "driver_stats",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column("driver", sa.String(32), nullable=False),
        sa.Column("task_type", sa.String(64), nullable=True),
        sa.Column("window_start", sa.Date(), nullable=False),
        sa.Column("dispatched", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("verified_landed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("total_duration_ms", sa.BigInteger(), nullable=False, server_default="0"),
        sa.UniqueConstraint(
            "tenant_id", "driver", "task_type", "window_start",
            name="uq_driver_stats_tenant_driver_task_window",
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_driver_stats_tenant_driver", "driver_stats",
        ["tenant_id", "driver"],
        schema="life_graph",
    )

    # ── verification_runs ────────────────────────────────────
    op.create_table(
        "verification_runs",
        sa.Column(
            "id", sa.dialects.postgresql.UUID(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(), nullable=False),
        sa.Column(
            "task_id", sa.dialects.postgresql.UUID(),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("results", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        schema="life_graph",
    )
    op.create_index(
        "ix_verification_runs_tenant_task", "verification_runs",
        ["tenant_id", "task_id"],
        schema="life_graph",
    )

    # ── ALTER agent_personas — add driver columns ────────────
    op.add_column(
        "agent_personas",
        sa.Column("driver", sa.String(32), nullable=True),
    )
    op.add_column(
        "agent_personas",
        sa.Column("verifier_chain", JSONB(), nullable=False, server_default="[]"),
    )
    op.add_column(
        "agent_personas",
        sa.Column("context_profile", JSONB(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "agent_personas",
        sa.Column("task_types", ARRAY(sa.Text()), nullable=False, server_default="{}"),
    )


def downgrade() -> None:
    # Drop new agent_personas columns
    op.drop_column("agent_personas", "task_types")
    op.drop_column("agent_personas", "context_profile")
    op.drop_column("agent_personas", "verifier_chain")
    op.drop_column("agent_personas", "driver")

    # Drop verification_runs
    op.drop_index("ix_verification_runs_tenant_task", schema="life_graph")
    op.drop_table("verification_runs", schema="life_graph")

    # Drop driver_stats
    op.drop_index("ix_driver_stats_tenant_driver", schema="life_graph")
    op.drop_table("driver_stats", schema="life_graph")

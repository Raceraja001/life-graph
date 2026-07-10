"""Add multi-tenancy support and job/usage tracking tables.

Revision ID: 003
Revises: 002
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── Add tenant_id to existing tables ───────────────────
    for table in ("memories", "sessions", "intentions", "knowledge_gaps"):
        op.add_column(
            table,
            sa.Column("tenant_id", sa.String(64), nullable=False, server_default="legacy"),
        )

    # ── Composite indexes for tenant-scoped queries ────────
    op.create_index("ix_memories_tenant_created", "memories", ["tenant_id", "created_at"])
    op.create_index("ix_memories_tenant_status", "memories", ["tenant_id", "status"])
    op.create_index("ix_sessions_tenant_started", "sessions", ["tenant_id", "started_at"])
    op.create_index("ix_intentions_tenant_status", "intentions", ["tenant_id", "status"])
    op.create_index("ix_knowledge_gaps_tenant", "knowledge_gaps", ["tenant_id", "resolved"])

    # ── Job Runs table ─────────────────────────────────────
    op.create_table(
        "job_runs",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("job_name", sa.String(100), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="queued"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "result",
            sa.dialects.postgresql.JSONB,
            nullable=False,
            server_default="{}",
        ),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("attempt", sa.Integer, nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_job_runs_tenant", "job_runs", ["tenant_id", "created_at"])
    op.create_index("ix_job_runs_status", "job_runs", ["status"])

    # ── Tenant Usage table ─────────────────────────────────
    op.create_table(
        "tenant_usage",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("api_calls", sa.Integer, nullable=False, server_default="0"),
        sa.Column("memories_created", sa.Integer, nullable=False, server_default="0"),
        sa.Column("llm_tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column(
            "llm_cost_usd", sa.Numeric(10, 6), nullable=False, server_default="0"
        ),
    )
    op.create_index(
        "ix_tenant_usage_lookup", "tenant_usage", ["tenant_id", "period_start"]
    )


def downgrade() -> None:
    op.drop_table("tenant_usage")
    op.drop_table("job_runs")

    op.drop_index("ix_knowledge_gaps_tenant", table_name="knowledge_gaps")
    op.drop_index("ix_intentions_tenant_status", table_name="intentions")
    op.drop_index("ix_sessions_tenant_started", table_name="sessions")
    op.drop_index("ix_memories_tenant_status", table_name="memories")
    op.drop_index("ix_memories_tenant_created", table_name="memories")

    for table in ("memories", "sessions", "intentions", "knowledge_gaps"):
        op.drop_column(table, "tenant_id")

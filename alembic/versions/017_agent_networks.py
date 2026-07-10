"""017 — Era 7: Agent Networks — tasks, messages, workflows, shared context.

Revision ID: 017
Revises: 016
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "017"
down_revision = "016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── agent_tasks — add new columns ───────────────────────
    op.add_column("agent_tasks", sa.Column("title", sa.Text(), nullable=True))
    op.add_column("agent_tasks", sa.Column("description", sa.Text(), nullable=True))
    op.add_column(
        "agent_tasks",
        sa.Column(
            "task_type", sa.String(30),
            nullable=False, server_default="'general'",
        ),
    )
    op.add_column("agent_tasks", sa.Column("instructions", sa.Text(), nullable=True))
    op.add_column(
        "agent_tasks",
        sa.Column("assigned_agent", sa.String(64), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("created_by_agent", sa.String(64), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("root_task_id", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_agent_tasks_root", "agent_tasks", "agent_tasks",
        ["root_task_id"], ["id"], ondelete="SET NULL",
    )
    op.add_column(
        "agent_tasks",
        sa.Column(
            "depth", sa.Integer(),
            nullable=False, server_default="0",
        ),
    )
    op.add_column(
        "agent_tasks",
        sa.Column(
            "on_child_failure", sa.String(20),
            nullable=False, server_default="'continue'",
        ),
    )
    op.add_column(
        "agent_tasks",
        sa.Column(
            "status_history", JSONB(),
            nullable=False, server_default="[]",
        ),
    )
    op.add_column("agent_tasks", sa.Column("cancel_reason", sa.Text(), nullable=True))
    op.add_column(
        "agent_tasks",
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("source_message_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("workflow_run_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column("workflow_step_id", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "agent_tasks",
        sa.Column(
            "properties", JSONB(),
            nullable=False, server_default="{}",
        ),
    )
    op.add_column(
        "agent_tasks",
        sa.Column(
            "tags", sa.ARRAY(sa.String(50)),
            nullable=False, server_default="{}",
        ),
    )

    # ── agent_tasks — new indexes ───────────────────────────
    op.create_index(
        "ix_agent_tasks_assigned", "agent_tasks",
        ["tenant_id", "assigned_agent"],
    )
    op.create_index(
        "ix_agent_tasks_root", "agent_tasks",
        ["root_task_id"],
    )
    op.create_index(
        "ix_agent_tasks_project", "agent_tasks",
        ["tenant_id", "project_id"],
    )
    op.create_index(
        "ix_agent_tasks_workflow", "agent_tasks",
        ["workflow_run_id"],
    )
    op.create_index(
        "ix_agent_tasks_created_desc", "agent_tasks",
        [sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_agent_tasks_properties", "agent_tasks",
        ["properties"],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_agent_tasks_tags", "agent_tasks",
        ["tags"],
        postgresql_using="gin",
    )

    # ── agent_messages ──────────────────────────────────────
    op.create_table(
        "agent_messages",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("sender_agent", sa.String(64), nullable=False),
        sa.Column("recipient_agent", sa.String(64), nullable=False),
        sa.Column("thread_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "reply_to_id", UUID(as_uuid=True),
            sa.ForeignKey("agent_messages.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("message_type", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(200), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column(
            "payload", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "attachments", JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "status", sa.String(20),
            nullable=False, server_default="'unread'",
        ),
        sa.Column(
            "priority", sa.String(10),
            nullable=False, server_default="'medium'",
        ),
        sa.Column(
            "task_id", UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "properties", JSONB(),
            nullable=False, server_default="{}",
        ),
    )
    op.create_index(
        "ix_agent_messages_inbox", "agent_messages",
        ["tenant_id", "recipient_agent", "status", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_agent_messages_outbox", "agent_messages",
        ["tenant_id", "sender_agent", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_agent_messages_thread", "agent_messages",
        ["thread_id"],
    )
    op.create_index(
        "ix_agent_messages_task", "agent_messages",
        ["task_id"],
    )
    op.create_index(
        "ix_agent_messages_type", "agent_messages",
        ["tenant_id", "message_type"],
    )
    op.create_index(
        "ix_agent_messages_unread", "agent_messages",
        ["tenant_id", "recipient_agent", sa.text("created_at DESC")],
        postgresql_where=sa.text("status = 'unread'"),
    )

    # ── cross_system_syncs ──────────────────────────────────
    op.create_table(
        "cross_system_syncs",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("sync_type", sa.String(40), nullable=False),
        sa.Column("target_system", sa.String(40), nullable=False),
        sa.Column("endpoint_url", sa.Text(), nullable=True),
        sa.Column(
            "status", sa.String(20),
            nullable=False, server_default="'pending'",
        ),
        sa.Column(
            "records_sent", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "records_synced", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "records_failed", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column("sync_duration_ms", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "retry_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_payload", JSONB(), nullable=True),
        sa.Column("response_summary", JSONB(), nullable=True),
        sa.Column("properties", JSONB(), nullable=True),
    )
    op.create_index(
        "ix_css_tenant_status", "cross_system_syncs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_css_tenant_target", "cross_system_syncs",
        ["tenant_id", "target_system", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_css_retry", "cross_system_syncs",
        ["tenant_id", "next_retry_at"],
        postgresql_where=sa.text("status = 'failed'"),
    )

    # ── workflows ───────────────────────────────────────────
    op.create_table(
        "workflows",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "version", sa.Integer(),
            nullable=False, server_default="1",
        ),
        sa.Column(
            "is_active", sa.Boolean(),
            nullable=False, server_default=sa.text("true"),
        ),
        sa.Column("created_by", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("properties", JSONB(), nullable=True),
        sa.Column(
            "tags", sa.ARRAY(sa.String(50)),
            nullable=True,
        ),
    )
    op.create_index(
        "uq_workflows_tenant_name", "workflows",
        ["tenant_id", "name"], unique=True,
    )
    op.create_index(
        "ix_workflows_tenant_active", "workflows",
        ["tenant_id", "is_active"],
    )

    # ── workflow_steps ──────────────────────────────────────
    op.create_table(
        "workflow_steps",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workflow_id", UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("assigned_agent", sa.String(64), nullable=True),
        sa.Column(
            "task_type", sa.String(30),
            nullable=False, server_default="'general'",
        ),
        sa.Column("instructions", sa.Text(), nullable=True),
        sa.Column(
            "timeout_seconds", sa.Integer(),
            nullable=False, server_default="3600",
        ),
        sa.Column(
            "retry_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "depends_on", sa.ARRAY(sa.String(64)),
            nullable=False, server_default="{}",
        ),
        sa.Column("condition", sa.Text(), nullable=True),
        sa.Column(
            "on_failure", sa.String(20),
            nullable=False, server_default="'abort'",
        ),
        sa.Column(
            "on_timeout", sa.String(20),
            nullable=False, server_default="'abort'",
        ),
        sa.Column("properties", JSONB(), nullable=True),
    )
    op.create_index(
        "uq_wfs_workflow_key", "workflow_steps",
        ["workflow_id", "step_key"], unique=True,
    )
    op.create_index(
        "ix_wfs_workflow_order", "workflow_steps",
        ["workflow_id", "step_order"],
    )

    # ── workflow_runs ───────────────────────────────────────
    op.create_table(
        "workflow_runs",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workflow_id", UUID(as_uuid=True),
            sa.ForeignKey("workflows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "status", sa.String(20),
            nullable=False, server_default="'pending'",
        ),
        sa.Column(
            "trigger", sa.String(40),
            nullable=False, server_default="'manual'",
        ),
        sa.Column("triggered_by", sa.String(64), nullable=True),
        sa.Column("input_params", JSONB(), nullable=True),
        sa.Column("output_summary", JSONB(), nullable=True),
        sa.Column("properties", JSONB(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_wfr_tenant_status", "workflow_runs",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_wfr_workflow", "workflow_runs",
        ["workflow_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_wfr_tenant_created", "workflow_runs",
        ["tenant_id", sa.text("created_at DESC")],
    )

    # ── workflow_step_runs ──────────────────────────────────
    op.create_table(
        "workflow_step_runs",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "workflow_run_id", UUID(as_uuid=True),
            sa.ForeignKey("workflow_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "workflow_step_id", UUID(as_uuid=True),
            sa.ForeignKey("workflow_steps.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status", sa.String(20),
            nullable=False, server_default="'pending'",
        ),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        sa.Column(
            "agent_task_id", UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("output", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "attempt", sa.Integer(),
            nullable=False, server_default="1",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("properties", JSONB(), nullable=True),
    )
    op.create_index(
        "uq_wfsr_run_step", "workflow_step_runs",
        ["workflow_run_id", "workflow_step_id"], unique=True,
    )
    op.create_index(
        "ix_wfsr_step", "workflow_step_runs",
        ["workflow_step_id"],
    )
    op.create_index(
        "ix_wfsr_task", "workflow_step_runs",
        ["agent_task_id"],
    )

    # ── shared_context ──────────────────────────────────────
    op.create_table(
        "shared_context",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("project_id", sa.String(128), nullable=True),
        sa.Column(
            "source_task_id", UUID(as_uuid=True),
            sa.ForeignKey("agent_tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_agent", sa.String(64), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "content_type", sa.String(30),
            nullable=False, server_default="'finding'",
        ),
        sa.Column(
            "tags", sa.ARRAY(sa.String(50)),
            nullable=True,
        ),
        sa.Column(
            "relevance_score", sa.Float(),
            nullable=False, server_default="1.0",
        ),
        sa.Column(
            "access_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column("content_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("last_accessed", sa.DateTime(timezone=True), nullable=True),
        sa.Column("properties", JSONB(), nullable=True),
    )
    # pgvector embedding column via raw SQL
    op.execute("ALTER TABLE shared_context ADD COLUMN embedding vector(768)")

    op.create_index(
        "ix_sc_tenant_project", "shared_context",
        ["tenant_id", "project_id"],
    )
    op.create_index(
        "ix_sc_task", "shared_context",
        ["source_task_id"],
    )
    op.create_index(
        "ix_sc_agent", "shared_context",
        ["tenant_id", "source_agent"],
    )
    op.create_index(
        "ix_sc_type", "shared_context",
        ["tenant_id", "content_type"],
    )
    op.create_index(
        "ix_sc_hash", "shared_context",
        ["content_hash"],
    )
    op.create_index(
        "ix_sc_tags", "shared_context",
        ["tags"],
        postgresql_using="gin",
    )


def downgrade() -> None:
    # ── shared_context ──────────────────────────────────────
    op.drop_index("ix_sc_tags")
    op.drop_index("ix_sc_hash")
    op.drop_index("ix_sc_type")
    op.drop_index("ix_sc_agent")
    op.drop_index("ix_sc_task")
    op.drop_index("ix_sc_tenant_project")
    op.drop_table("shared_context")

    # ── workflow_step_runs ──────────────────────────────────
    op.drop_index("ix_wfsr_task")
    op.drop_index("ix_wfsr_step")
    op.drop_index("uq_wfsr_run_step")
    op.drop_table("workflow_step_runs")

    # ── workflow_runs ───────────────────────────────────────
    op.drop_index("ix_wfr_tenant_created")
    op.drop_index("ix_wfr_workflow")
    op.drop_index("ix_wfr_tenant_status")
    op.drop_table("workflow_runs")

    # ── workflow_steps ──────────────────────────────────────
    op.drop_index("ix_wfs_workflow_order")
    op.drop_index("uq_wfs_workflow_key")
    op.drop_table("workflow_steps")

    # ── workflows ───────────────────────────────────────────
    op.drop_index("ix_workflows_tenant_active")
    op.drop_index("uq_workflows_tenant_name")
    op.drop_table("workflows")

    # ── cross_system_syncs ──────────────────────────────────
    op.drop_index("ix_css_retry")
    op.drop_index("ix_css_tenant_target")
    op.drop_index("ix_css_tenant_status")
    op.drop_table("cross_system_syncs")

    # ── agent_messages ──────────────────────────────────────
    op.drop_index("ix_agent_messages_unread")
    op.drop_index("ix_agent_messages_type")
    op.drop_index("ix_agent_messages_task")
    op.drop_index("ix_agent_messages_thread")
    op.drop_index("ix_agent_messages_outbox")
    op.drop_index("ix_agent_messages_inbox")
    op.drop_table("agent_messages")

    # ── agent_tasks — drop new indexes ──────────────────────
    op.drop_index("ix_agent_tasks_tags")
    op.drop_index("ix_agent_tasks_properties")
    op.drop_index("ix_agent_tasks_created_desc")
    op.drop_index("ix_agent_tasks_workflow")
    op.drop_index("ix_agent_tasks_project")
    op.drop_index("ix_agent_tasks_root")
    op.drop_index("ix_agent_tasks_assigned")

    # ── agent_tasks — drop FK then new columns ──────────────
    op.drop_constraint("fk_agent_tasks_root", "agent_tasks", type_="foreignkey")
    op.drop_column("agent_tasks", "tags")
    op.drop_column("agent_tasks", "properties")
    op.drop_column("agent_tasks", "workflow_step_id")
    op.drop_column("agent_tasks", "workflow_run_id")
    op.drop_column("agent_tasks", "source_message_id")
    op.drop_column("agent_tasks", "deadline")
    op.drop_column("agent_tasks", "claimed_at")
    op.drop_column("agent_tasks", "cancel_reason")
    op.drop_column("agent_tasks", "status_history")
    op.drop_column("agent_tasks", "on_child_failure")
    op.drop_column("agent_tasks", "depth")
    op.drop_column("agent_tasks", "root_task_id")
    op.drop_column("agent_tasks", "created_by_agent")
    op.drop_column("agent_tasks", "assigned_agent")
    op.drop_column("agent_tasks", "instructions")
    op.drop_column("agent_tasks", "task_type")
    op.drop_column("agent_tasks", "description")
    op.drop_column("agent_tasks", "title")

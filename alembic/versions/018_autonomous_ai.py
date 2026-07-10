"""018 — Era 8: Autonomous AI — safety rules, auto-actions, trust scores,
approval queue, audit log, autonomy levels.

Revision ID: 018
Revises: 017
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "018"
down_revision = "017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── action_safety_rules ────────────────────────────────────
    op.create_table(
        "action_safety_rules",
        sa.Column(
            "id", sa.Text(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("action_name", sa.Text(), nullable=False),
        sa.Column("action_pattern", sa.Text(), nullable=False),
        sa.Column(
            "category", sa.Text(),
            nullable=False, server_default="general",
        ),
        sa.Column(
            "risk_level", sa.Text(),
            nullable=False, server_default="dangerous",
        ),
        sa.Column(
            "trust_threshold", sa.Numeric(3, 2),
            nullable=False, server_default="0.70",
        ),
        sa.Column(
            "is_guardrail", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("max_blast_radius", sa.Integer(), nullable=True),
        sa.Column(
            "requires_staging", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column(
            "is_reversible", sa.Boolean(),
            nullable=False, server_default=sa.text("true"),
        ),
        sa.Column("rollback_template", sa.Text(), nullable=True),
        sa.Column(
            "enabled", sa.Boolean(),
            nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "priority", sa.Integer(),
            nullable=False, server_default="100",
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("tenant_id", "action_name", name="uq_asr_tenant_action"),
        sa.CheckConstraint(
            "risk_level IN ('safe', 'moderate', 'dangerous')",
            name="ck_asr_risk_level",
        ),
    )
    op.create_index("ix_asr_tenant", "action_safety_rules", ["tenant_id"])
    op.create_index("ix_asr_risk", "action_safety_rules", ["tenant_id", "risk_level"])
    op.create_index("ix_asr_category", "action_safety_rules", ["tenant_id", "category"])
    op.create_index("ix_asr_enabled", "action_safety_rules", ["tenant_id", "enabled"])
    op.create_index("ix_asr_pattern", "action_safety_rules", ["action_pattern"])

    # ── approval_queue (created before auto_actions due to FK) ─
    op.create_table(
        "approval_queue",
        sa.Column(
            "id", sa.Text(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("action_name", sa.Text(), nullable=False),
        sa.Column("action_command", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=True),
        sa.Column(
            "category", sa.Text(),
            nullable=False, server_default="general",
        ),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("trigger_detail", sa.Text(), nullable=False),
        sa.Column("estimated_impact", sa.Text(), nullable=True),
        sa.Column(
            "safety_rule_id", sa.Text(),
            sa.ForeignKey("action_safety_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status", sa.Text(),
            nullable=False, server_default="pending",
        ),
        sa.Column(
            "priority", sa.Integer(),
            nullable=False, server_default="100",
        ),
        sa.Column("resolved_by", sa.Text(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "also_trust", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("batch_id", sa.Text(), nullable=True),
        sa.Column(
            "timeout_hours", sa.Integer(),
            nullable=False, server_default="24",
        ),
        sa.Column(
            "escalation_sent", JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "risk_level IN ('moderate', 'dangerous')",
            name="ck_aq_risk_level",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'expired', 'stale', 'batch_approved')",
            name="ck_aq_status",
        ),
    )
    op.create_index("ix_aq_tenant_status", "approval_queue", ["tenant_id", "status"])
    op.create_index("ix_aq_tenant_agent", "approval_queue", ["tenant_id", "agent_id"])
    op.create_index("ix_aq_project", "approval_queue", ["tenant_id", "project_id"])
    op.create_index("ix_aq_risk", "approval_queue", ["tenant_id", "risk_level"])
    op.create_index("ix_aq_batch", "approval_queue", ["batch_id"])
    op.create_index(
        "ix_aq_expires", "approval_queue",
        ["expires_at"],
        postgresql_where=sa.text("status = 'pending'"),
    )

    # ── auto_actions ───────────────────────────────────────────
    op.create_table(
        "auto_actions",
        sa.Column(
            "id", sa.Text(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("action_name", sa.Text(), nullable=False),
        sa.Column("action_command", sa.Text(), nullable=False),
        sa.Column("risk_level", sa.Text(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("trigger_detail", sa.Text(), nullable=False),
        sa.Column(
            "safety_rule_id", sa.Text(),
            sa.ForeignKey("action_safety_rules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("before_state", JSONB(), nullable=True),
        sa.Column("after_state", JSONB(), nullable=True),
        sa.Column(
            "status", sa.Text(),
            nullable=False, server_default="pending",
        ),
        sa.Column("exit_code", sa.Integer(), nullable=True),
        sa.Column("stdout", sa.Text(), nullable=True),
        sa.Column("stderr", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "is_reversible", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("rollback_command", sa.Text(), nullable=True),
        sa.Column("rolled_back_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rollback_action_id", sa.Text(), nullable=True),
        sa.Column(
            "approval_id", sa.Text(),
            sa.ForeignKey("approval_queue.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("approved_by", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "risk_level IN ('safe', 'moderate', 'dangerous')",
            name="ck_aa_risk_level",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'executing', 'success', 'failure', "
            "'timeout', 'rolled_back', 'skipped')",
            name="ck_aa_status",
        ),
    )
    op.create_index("ix_aa_tenant_agent", "auto_actions", ["tenant_id", "agent_id"])
    op.create_index("ix_aa_tenant_status", "auto_actions", ["tenant_id", "status"])
    op.create_index("ix_aa_project", "auto_actions", ["tenant_id", "project_id"])
    op.create_index("ix_aa_safety_rule", "auto_actions", ["safety_rule_id"])
    op.create_index("ix_aa_approval", "auto_actions", ["approval_id"])
    op.create_index(
        "ix_aa_created", "auto_actions",
        ["tenant_id", sa.text("created_at DESC")],
    )

    # ── trust_scores ───────────────────────────────────────────
    op.create_table(
        "trust_scores",
        sa.Column(
            "id", sa.Text(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column(
            "score", sa.Numeric(4, 3),
            nullable=False, server_default="0.000",
        ),
        sa.Column(
            "total_successes", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "total_failures", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "consecutive_successes", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "consecutive_failures", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "peak_score", sa.Numeric(4, 3),
            nullable=False, server_default="0.000",
        ),
        sa.Column("last_action_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decay_rate", sa.Numeric(4, 3),
            nullable=False, server_default="0.050",
        ),
        sa.Column(
            "failure_penalty", sa.Numeric(4, 3),
            nullable=False, server_default="0.500",
        ),
        sa.Column("manual_override", sa.Numeric(4, 3), nullable=True),
        sa.Column("override_reason", sa.Text(), nullable=True),
        sa.Column("override_by", sa.Text(), nullable=True),
        sa.Column("override_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint(
            "tenant_id", "agent_id", "action_type", "project_id",
            name="uq_ts_tenant_agent_action_project",
        ),
    )
    op.create_index("ix_ts_agent", "trust_scores", ["tenant_id", "agent_id"])
    op.create_index("ix_ts_action", "trust_scores", ["tenant_id", "action_type"])
    op.create_index("ix_ts_project", "trust_scores", ["tenant_id", "project_id"])
    op.create_index(
        "ix_ts_score", "trust_scores",
        ["tenant_id", sa.text("score DESC")],
    )

    # ── audit_log ──────────────────────────────────────────────
    op.create_table(
        "audit_log",
        sa.Column(
            "id", sa.Text(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("agent_id", sa.Text(), nullable=True),
        sa.Column(
            "actor_type", sa.Text(),
            nullable=False, server_default="agent",
        ),
        sa.Column("actor_id", sa.Text(), nullable=False),
        sa.Column("action_type", sa.Text(), nullable=False),
        sa.Column("action_name", sa.Text(), nullable=False),
        sa.Column("action_command", sa.Text(), nullable=True),
        sa.Column("risk_level", sa.Text(), nullable=True),
        sa.Column("trigger_type", sa.Text(), nullable=True),
        sa.Column("trigger_detail", sa.Text(), nullable=True),
        sa.Column("classification_reasoning", JSONB(), nullable=True),
        sa.Column("project_id", sa.Text(), nullable=True),
        sa.Column("auto_action_id", sa.Text(), nullable=True),
        sa.Column("approval_id", sa.Text(), nullable=True),
        sa.Column("related_audit_id", sa.Text(), nullable=True),
        sa.Column("before_state", JSONB(), nullable=True),
        sa.Column("after_state", JSONB(), nullable=True),
        sa.Column("result", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "actor_type IN ('agent', 'operator', 'system')",
            name="ck_al_actor_type",
        ),
        sa.CheckConstraint(
            "result IN ('success', 'failure', 'timeout', 'rejected', "
            "'expired', 'rolled_back')",
            name="ck_al_result",
        ),
    )
    op.create_index(
        "ix_al_tenant", "audit_log",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index("ix_al_agent", "audit_log", ["tenant_id", "agent_id"])
    op.create_index("ix_al_action", "audit_log", ["tenant_id", "action_type"])
    op.create_index("ix_al_project", "audit_log", ["tenant_id", "project_id"])
    op.create_index("ix_al_auto_action", "audit_log", ["auto_action_id"])
    op.create_index("ix_al_approval", "audit_log", ["approval_id"])
    op.create_index("ix_al_result", "audit_log", ["tenant_id", "result"])

    # ── autonomy_levels ────────────────────────────────────────
    op.create_table(
        "autonomy_levels",
        sa.Column(
            "id", sa.Text(),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()::text"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("project_id", sa.Text(), nullable=False),
        sa.Column(
            "level", sa.Text(),
            nullable=False, server_default="L0",
        ),
        sa.Column(
            "level_description", sa.Text(),
            nullable=False, server_default="Ask Everything",
        ),
        sa.Column(
            "safe_successes", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "moderate_successes", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "dangerous_successes", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "promotion_eligible", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column(
            "promotion_threshold", JSONB(),
            nullable=False,
            server_default=sa.text(
                "'{\"L0_to_L1\": 20, \"L1_to_L2\": 50, \"L2_to_L3\": 100}'::jsonb"
            ),
        ),
        sa.Column("last_failure_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "demotion_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column("manual_level", sa.Text(), nullable=True),
        sa.Column("manual_set_by", sa.Text(), nullable=True),
        sa.Column("manual_reason", sa.Text(), nullable=True),
        sa.Column("manual_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "moderate_timeout_minutes", sa.Integer(),
            nullable=False, server_default="15",
        ),
        sa.Column(
            "l3_opted_in", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column(
            "l3_min_trust", sa.Numeric(3, 2),
            nullable=False, server_default="0.90",
        ),
        sa.Column(
            "total_auto_actions", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "total_successes", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "total_failures", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column("success_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("last_promotion_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_demotion_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_audit_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.UniqueConstraint("tenant_id", "project_id", name="uq_al_tenant_project"),
        sa.CheckConstraint(
            "level IN ('L0', 'L1', 'L2', 'L3')",
            name="ck_al_level",
        ),
    )
    op.create_index(
        "ix_alvl_tenant_level", "autonomy_levels",
        ["tenant_id", "level"],
    )
    op.create_index(
        "ix_alvl_tenant_project", "autonomy_levels",
        ["tenant_id", "project_id"],
    )
    op.create_index(
        "ix_alvl_promo", "autonomy_levels",
        ["tenant_id", "promotion_eligible"],
    )


def downgrade() -> None:
    # ── autonomy_levels ────────────────────────────────────────
    op.drop_index("ix_alvl_promo")
    op.drop_index("ix_alvl_tenant_project")
    op.drop_index("ix_alvl_tenant_level")
    op.drop_table("autonomy_levels")

    # ── audit_log ──────────────────────────────────────────────
    op.drop_index("ix_al_result")
    op.drop_index("ix_al_approval")
    op.drop_index("ix_al_auto_action")
    op.drop_index("ix_al_project")
    op.drop_index("ix_al_action")
    op.drop_index("ix_al_agent")
    op.drop_index("ix_al_tenant")
    op.drop_table("audit_log")

    # ── trust_scores ───────────────────────────────────────────
    op.drop_index("ix_ts_score")
    op.drop_index("ix_ts_project")
    op.drop_index("ix_ts_action")
    op.drop_index("ix_ts_agent")
    op.drop_table("trust_scores")

    # ── auto_actions ───────────────────────────────────────────
    op.drop_index("ix_aa_created")
    op.drop_index("ix_aa_approval")
    op.drop_index("ix_aa_safety_rule")
    op.drop_index("ix_aa_project")
    op.drop_index("ix_aa_tenant_status")
    op.drop_index("ix_aa_tenant_agent")
    op.drop_table("auto_actions")

    # ── approval_queue ─────────────────────────────────────────
    op.drop_index("ix_aq_expires")
    op.drop_index("ix_aq_batch")
    op.drop_index("ix_aq_risk")
    op.drop_index("ix_aq_project")
    op.drop_index("ix_aq_tenant_agent")
    op.drop_index("ix_aq_tenant_status")
    op.drop_table("approval_queue")

    # ── action_safety_rules ────────────────────────────────────
    op.drop_index("ix_asr_pattern")
    op.drop_index("ix_asr_enabled")
    op.drop_index("ix_asr_category")
    op.drop_index("ix_asr_risk")
    op.drop_index("ix_asr_tenant")
    op.drop_table("action_safety_rules")

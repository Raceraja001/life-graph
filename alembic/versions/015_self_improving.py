"""015 — Era 5: Self-Improving Agent — eval suites, prompt versioning, optimization.

Revision ID: 015
Revises: 014
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── eval_suites ──────────────────────────────────────────
    op.create_table(
        "eval_suites",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "accuracy_threshold_pct", sa.Numeric(5, 2),
            nullable=False, server_default="90.00",
        ),
        sa.Column(
            "auto_optimize_enabled", sa.Boolean(),
            nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "consecutive_failures", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "max_consecutive_fails", sa.Integer(),
            nullable=False, server_default="3",
        ),
        sa.Column(
            "case_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "last_run_at", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_accuracy_pct", sa.Numeric(5, 2),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "uq_eval_suites_tenant_task", "eval_suites",
        ["tenant_id", "task_type"], unique=True,
    )
    op.create_index(
        "ix_eval_suites_tenant", "eval_suites",
        ["tenant_id"],
    )
    op.create_index(
        "ix_eval_suites_auto_opt", "eval_suites",
        ["auto_optimize_enabled"],
        postgresql_where=sa.text("auto_optimize_enabled = true"),
    )

    # ── eval_cases ───────────────────────────────────────────
    op.create_table(
        "eval_cases",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "suite_id", UUID(as_uuid=True),
            sa.ForeignKey("eval_suites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_text", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.Text(), nullable=False),
        sa.Column(
            "scoring_type", sa.Text(),
            nullable=False, server_default="'exact_match'",
        ),
        sa.Column(
            "scoring_config", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "metadata", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "source", sa.Text(),
            nullable=False, server_default="'manual'",
        ),
        sa.Column(
            "is_active", sa.Boolean(),
            nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "scoring_type IN ('exact_match','contains','regex',"
            "'semantic_similarity','llm_judge')",
            name="ck_eval_cases_scoring_type",
        ),
    )
    op.create_index(
        "ix_eval_cases_suite_active", "eval_cases",
        ["suite_id"],
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "ix_eval_cases_suite_scoring", "eval_cases",
        ["suite_id", "scoring_type"],
    )

    # ── eval_runs ────────────────────────────────────────────
    op.create_table(
        "eval_runs",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "suite_id", UUID(as_uuid=True),
            sa.ForeignKey("eval_suites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("prompt_version_id", sa.Text(), nullable=False),
        sa.Column(
            "trigger", sa.Text(),
            nullable=False, server_default="'manual'",
        ),
        sa.Column(
            "status", sa.Text(),
            nullable=False, server_default="'running'",
        ),
        sa.Column("total_cases", sa.Integer(), nullable=True),
        sa.Column("passed", sa.Integer(), nullable=True),
        sa.Column("failed", sa.Integer(), nullable=True),
        sa.Column("errored", sa.Integer(), nullable=True),
        sa.Column("accuracy_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("p95_latency_ms", sa.Float(), nullable=True),
        sa.Column("total_tokens", sa.Integer(), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "trigger IN ('manual','nightly_cron','optimization_test',"
            "'regression_check')",
            name="ck_eval_runs_trigger",
        ),
        sa.CheckConstraint(
            "status IN ('running','completed','error','cancelled')",
            name="ck_eval_runs_status",
        ),
    )
    op.create_index(
        "ix_eval_runs_suite_started", "eval_runs",
        ["suite_id", sa.text("started_at DESC")],
    )
    op.create_index(
        "ix_eval_runs_prompt_ver", "eval_runs",
        ["prompt_version_id"],
    )
    op.create_index(
        "ix_eval_runs_trigger_started", "eval_runs",
        ["trigger", sa.text("started_at DESC")],
    )

    # ── eval_results ─────────────────────────────────────────
    op.create_table(
        "eval_results",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "run_id", UUID(as_uuid=True),
            sa.ForeignKey("eval_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "case_id", UUID(as_uuid=True),
            sa.ForeignKey("eval_cases.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("actual_output", sa.Text(), nullable=True),
        sa.Column("score", sa.Numeric(5, 4), nullable=True),
        sa.Column("failure_type", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("similarity_score", sa.Numeric(5, 4), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('pass','fail','error')",
            name="ck_eval_results_status",
        ),
    )
    op.create_index(
        "ix_eval_results_run", "eval_results",
        ["run_id"],
    )
    op.create_index(
        "ix_eval_results_case", "eval_results",
        ["case_id"],
    )
    op.create_index(
        "ix_eval_results_run_status", "eval_results",
        ["run_id", "status"],
    )
    op.create_index(
        "ix_eval_results_run_failure", "eval_results",
        ["run_id", "failure_type"],
        postgresql_where=sa.text("status = 'fail'"),
    )

    # ── prompt_versions ──────────────────────────────────────
    op.create_table(
        "prompt_versions",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column(
            "few_shot_examples", JSONB(),
            nullable=False, server_default="[]",
        ),
        sa.Column(
            "is_active", sa.Boolean(),
            nullable=False, server_default=sa.text("false"),
        ),
        sa.Column("eval_score", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "created_by", sa.Text(),
            nullable=False, server_default="'human'",
        ),
        sa.Column("optimization_run_id", sa.Text(), nullable=True),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column(
            "activated_at", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "deactivated_at", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "uq_prompt_ver_active", "prompt_versions",
        ["tenant_id", "task_type"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "uq_prompt_ver_number", "prompt_versions",
        ["tenant_id", "task_type", "version_number"],
        unique=True,
    )
    op.create_index(
        "ix_prompt_ver_lookup", "prompt_versions",
        ["tenant_id", "task_type", sa.text("version_number DESC")],
    )

    # ── optimization_runs ────────────────────────────────────
    op.create_table(
        "optimization_runs",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "suite_id", UUID(as_uuid=True),
            sa.ForeignKey("eval_suites.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("trigger_eval_run_id", sa.Text(), nullable=False),
        sa.Column("trigger_accuracy_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("threshold_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("training_positive_count", sa.Integer(), nullable=True),
        sa.Column("training_negative_count", sa.Integer(), nullable=True),
        sa.Column("candidate_version_id", sa.Text(), nullable=True),
        sa.Column("candidate_eval_run_id", sa.Text(), nullable=True),
        sa.Column("candidate_accuracy_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("previous_version_id", sa.Text(), nullable=True),
        sa.Column("previous_accuracy_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "status", sa.Text(),
            nullable=False, server_default="'running'",
        ),
        sa.Column("regression_details", JSONB(), nullable=True),
        sa.Column("review_decision", sa.Text(), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_at", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("optimization_tokens", sa.Integer(), nullable=True),
        sa.Column("eval_tokens", sa.Integer(), nullable=True),
        sa.Column("optimization_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("eval_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('running','testing','deployed','no_improvement',"
            "'needs_review','rejected','error')",
            name="ck_optimization_runs_status",
        ),
    )
    op.create_index(
        "ix_opt_runs_tenant_started", "optimization_runs",
        ["tenant_id", sa.text("started_at DESC")],
    )
    op.create_index(
        "ix_opt_runs_task_started", "optimization_runs",
        ["task_type", sa.text("started_at DESC")],
    )
    op.create_index(
        "ix_opt_runs_status", "optimization_runs",
        ["status"],
    )
    op.create_index(
        "ix_opt_runs_needs_review", "optimization_runs",
        ["status"],
        postgresql_where=sa.text("status = 'needs_review'"),
    )

    # ── nightly_run_log ──────────────────────────────────────
    op.create_table(
        "nightly_run_log",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "status", sa.Text(),
            nullable=False, server_default="'running'",
        ),
        sa.Column(
            "task_types_evaluated", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "optimizations_triggered", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "optimizations_deployed", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "optimizations_flagged", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column("total_eval_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("total_opt_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("total_cost_usd", sa.Numeric(10, 6), nullable=True),
        sa.Column("duration_seconds", sa.Float(), nullable=True),
        sa.Column("summary", JSONB(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "completed_at", sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('running','completed','partial','error')",
            name="ck_nightly_run_log_status",
        ),
    )
    op.create_index(
        "ix_nightly_log_tenant_started", "nightly_run_log",
        ["tenant_id", sa.text("started_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_nightly_log_tenant_started")
    op.drop_table("nightly_run_log")

    op.drop_index("ix_opt_runs_needs_review")
    op.drop_index("ix_opt_runs_status")
    op.drop_index("ix_opt_runs_task_started")
    op.drop_index("ix_opt_runs_tenant_started")
    op.drop_table("optimization_runs")

    op.drop_index("ix_prompt_ver_lookup")
    op.drop_index("uq_prompt_ver_number")
    op.drop_index("uq_prompt_ver_active")
    op.drop_table("prompt_versions")

    op.drop_index("ix_eval_results_run_failure")
    op.drop_index("ix_eval_results_run_status")
    op.drop_index("ix_eval_results_case")
    op.drop_index("ix_eval_results_run")
    op.drop_table("eval_results")

    op.drop_index("ix_eval_runs_trigger_started")
    op.drop_index("ix_eval_runs_prompt_ver")
    op.drop_index("ix_eval_runs_suite_started")
    op.drop_table("eval_runs")

    op.drop_index("ix_eval_cases_suite_scoring")
    op.drop_index("ix_eval_cases_suite_active")
    op.drop_table("eval_cases")

    op.drop_index("ix_eval_suites_auto_opt")
    op.drop_index("ix_eval_suites_tenant")
    op.drop_index("uq_eval_suites_tenant_task")
    op.drop_table("eval_suites")

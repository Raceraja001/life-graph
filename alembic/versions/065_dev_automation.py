"""065 — dev automation: intake sources, backlog, dev-task schedules, breakers.

docs/specs/dev-automation.md (Phase 4a of the race-app migration): race-app's
intake, night-shift scheduler, circuit breaker and morning digest rebuilt in
life-graph. ``dev_automation_settings`` holds one row per tenant (limits,
digest, breaker, timezone; JSONB validated by services/dev/automation),
``dev_intake_sources`` and ``dev_schedules`` the owner's configuration,
``dev_backlog`` what the sources found (``external_key`` unique per tenant,
so a key is never added twice), ``dev_schedule_runs`` every handled slot
(partial unique indexes make "once per job per day" and "once per
predecessor task" hold across restarts and overlapping ticks), and
``dev_automation_breakers`` the circuit breaker per source / job.

Every feature is off with no rows. Numbered 065, revising 064; the parallel
``race/automation-teams`` branch takes 066 at merge time.

No schema qualifier, matching every migration since 023.

Revision ID: 065
Revises: 064
Create Date: 2026-11-27
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID

from alembic import op

revision = "065"
down_revision = "064"
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column(
        "id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")
    )


def _stamp(name: str) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now())


def upgrade() -> None:
    op.create_table(
        "dev_automation_settings",
        sa.Column("tenant_id", sa.String(64), primary_key=True),
        sa.Column("settings", JSONB(), nullable=False, server_default="{}"),
        sa.Column("state", JSONB(), nullable=False, server_default="{}"),
        sa.Column("updated_by", sa.String(128), nullable=True),
        _stamp("created_at"),
        _stamp("updated_at"),
    )

    op.create_table(
        "dev_intake_sources",
        _id(),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("name", sa.String(80), nullable=True),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("filter", sa.String(100), nullable=True),
        sa.Column("persona", sa.String(100), nullable=True),
        sa.Column("mode", sa.String(8), nullable=False, server_default="ask"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("poll_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("comment_on_issue", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("last_polled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.CheckConstraint(
            "kind IN ('github_issues','failing_ci','life_graph_intentions','todo_comments')",
            name="ck_dev_intake_sources_kind",
        ),
        sa.CheckConstraint("mode IN ('plan','ask','auto')", name="ck_dev_intake_sources_mode"),
        sa.CheckConstraint(
            "poll_minutes BETWEEN 5 AND 1440", name="ck_dev_intake_sources_poll_minutes"
        ),
    )
    op.create_index("ix_dev_intake_sources_tenant", "dev_intake_sources", ["tenant_id"])

    op.create_table(
        "dev_backlog",
        _id(),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "source_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dev_intake_sources.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("external_key", sa.String(300), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("task_id", UUID(as_uuid=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("properties", JSONB(), nullable=False, server_default="{}"),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.UniqueConstraint("tenant_id", "external_key", name="uq_dev_backlog_tenant_key"),
        sa.CheckConstraint(
            "status IN ('new','queued','running','done','skipped','failed')",
            name="ck_dev_backlog_status",
        ),
    )
    op.create_index("ix_dev_backlog_tenant_status", "dev_backlog", ["tenant_id", "status"])

    op.create_table(
        "dev_schedules",
        _id(),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("persona", sa.String(100), nullable=True),
        sa.Column("mode", sa.String(8), nullable=False, server_default="ask"),
        sa.Column("days", ARRAY(sa.Integer()), nullable=False),
        sa.Column("time", sa.String(5), nullable=False),
        sa.Column(
            "after_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dev_schedules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        _stamp("created_at"),
        _stamp("updated_at"),
        sa.CheckConstraint("mode IN ('plan','ask','auto')", name="ck_dev_schedules_mode"),
    )
    op.create_index("ix_dev_schedules_tenant", "dev_schedules", ["tenant_id"])

    op.create_table(
        "dev_schedule_runs",
        _id(),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column(
            "schedule_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dev_schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("slot_date", sa.String(10), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("predecessor_task_id", UUID(as_uuid=True), nullable=True),
        sa.Column("outcome", sa.String(32), nullable=False),
        sa.Column("task_id", UUID(as_uuid=True), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        _stamp("created_at"),
        _stamp("updated_at"),
    )
    op.create_index(
        "uq_dev_schedule_runs_slot",
        "dev_schedule_runs",
        ["schedule_id", "slot_date"],
        unique=True,
        postgresql_where=sa.text("trigger = 'scheduled'"),
    )
    op.create_index(
        "uq_dev_schedule_runs_chain",
        "dev_schedule_runs",
        ["schedule_id", "predecessor_task_id"],
        unique=True,
        postgresql_where=sa.text("trigger = 'chain'"),
    )
    op.create_index(
        "ix_dev_schedule_runs_job",
        "dev_schedule_runs",
        ["tenant_id", "schedule_id", "created_at"],
    )

    op.create_table(
        "dev_automation_breakers",
        _id(),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("label", sa.String(120), nullable=False),
        sa.Column("tripped", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_reason", sa.Text(), nullable=True),
        sa.Column("tripped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("counted", JSONB(), nullable=False, server_default="[]"),
        _stamp("updated_at"),
        sa.UniqueConstraint("tenant_id", "key", name="uq_dev_automation_breakers_key"),
    )


def downgrade() -> None:
    op.drop_table("dev_automation_breakers")
    op.drop_index("ix_dev_schedule_runs_job", table_name="dev_schedule_runs")
    op.drop_index("uq_dev_schedule_runs_chain", table_name="dev_schedule_runs")
    op.drop_index("uq_dev_schedule_runs_slot", table_name="dev_schedule_runs")
    op.drop_table("dev_schedule_runs")
    op.drop_index("ix_dev_schedules_tenant", table_name="dev_schedules")
    op.drop_table("dev_schedules")
    op.drop_index("ix_dev_backlog_tenant_status", table_name="dev_backlog")
    op.drop_table("dev_backlog")
    op.drop_index("ix_dev_intake_sources_tenant", table_name="dev_intake_sources")
    op.drop_table("dev_intake_sources")
    op.drop_table("dev_automation_settings")

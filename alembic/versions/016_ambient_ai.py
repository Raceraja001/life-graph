"""016 — Era 6: Ambient AI — watch configs, events, runs, tech radar, notifications.

Revision ID: 016
Revises: 015
Create Date: 2026-07-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "016"
down_revision = "015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── watch_configs ────────────────────────────────────────
    op.create_table(
        "watch_configs",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.String(64), nullable=False),
        sa.Column("watcher_name", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schedule", sa.Text(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(),
            nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "config", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "consecutive_failures", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
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
        "uq_watch_configs_tenant_name", "watch_configs",
        ["tenant_id", "watcher_name"], unique=True,
    )
    op.create_index(
        "ix_watch_configs_tenant", "watch_configs",
        ["tenant_id"],
    )
    op.create_index(
        "ix_watch_configs_enabled", "watch_configs",
        ["tenant_id", "enabled"],
        postgresql_where=sa.text("enabled = true"),
    )

    # ── watch_events ─────────────────────────────────────────
    op.create_table(
        "watch_events",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("watcher_name", sa.Text(), nullable=False),
        sa.Column("run_id", UUID(as_uuid=True), nullable=True),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column(
            "details", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "severity IN ('critical','important','info')",
            name="ck_watch_events_severity",
        ),
    )
    op.create_index(
        "ix_watch_events_tenant_created", "watch_events",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_watch_events_tenant_severity", "watch_events",
        ["tenant_id", "severity", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_watch_events_tenant_watcher", "watch_events",
        ["tenant_id", "watcher_name", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_watch_events_unacked", "watch_events",
        ["tenant_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("acknowledged_at IS NULL"),
    )
    op.create_index(
        "ix_watch_events_run", "watch_events",
        ["run_id"],
    )

    # ── watcher_runs ─────────────────────────────────────────
    op.create_table(
        "watcher_runs",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("watcher_name", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(),
            nullable=False, server_default="'running'",
        ),
        sa.Column(
            "started_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "events_generated", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "result", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "status IN ('running','success','failed')",
            name="ck_watcher_runs_status",
        ),
    )
    op.create_index(
        "ix_watcher_runs_tenant_watcher", "watcher_runs",
        ["tenant_id", "watcher_name", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_watcher_runs_failed", "watcher_runs",
        ["tenant_id", sa.text("created_at DESC")],
        postgresql_where=sa.text("status = 'failed'"),
    )

    # ── tech_radar ───────────────────────────────────────────
    op.create_table(
        "tech_radar",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=True),
        sa.Column("subreddit", sa.Text(), nullable=True),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column(
            "upvotes", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "comments", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column(
            "tags", sa.ARRAY(sa.Text()),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "scraped_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint(
            "source IN ('hn','reddit','github_trending')",
            name="ck_tech_radar_source",
        ),
    )
    op.create_index(
        "uq_tech_radar_tenant_url", "tech_radar",
        ["tenant_id", "url"], unique=True,
    )
    op.create_index(
        "ix_tech_radar_tenant_scraped", "tech_radar",
        ["tenant_id", sa.text("scraped_at DESC")],
    )
    op.create_index(
        "ix_tech_radar_tenant_score", "tech_radar",
        ["tenant_id", sa.text("score DESC")],
    )
    op.create_index(
        "ix_tech_radar_tenant_source", "tech_radar",
        ["tenant_id", "source", sa.text("scraped_at DESC")],
    )
    op.create_index(
        "ix_tech_radar_tags", "tech_radar",
        ["tags"],
        postgresql_using="gin",
    )

    # ── watcher_notifications ────────────────────────────────
    op.create_table(
        "watcher_notifications",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column(
            "event_id", UUID(as_uuid=True),
            sa.ForeignKey("watch_events.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column(
            "status", sa.Text(),
            nullable=False, server_default="'pending'",
        ),
        sa.Column("recipient", sa.Text(), nullable=True),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "retry_count", sa.Integer(),
            nullable=False, server_default="0",
        ),
        sa.Column(
            "max_retries", sa.Integer(),
            nullable=False, server_default="3",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("digest_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.text("NOW()"),
        ),
    )
    op.create_index(
        "ix_watcher_notif_tenant_created", "watcher_notifications",
        ["tenant_id", sa.text("created_at DESC")],
    )
    op.create_index(
        "ix_watcher_notif_pending", "watcher_notifications",
        ["tenant_id", "status"],
        postgresql_where=sa.text("status IN ('pending','queued','failed')"),
    )
    op.create_index(
        "ix_watcher_notif_digest", "watcher_notifications",
        ["digest_id"],
        postgresql_where=sa.text("digest_id IS NOT NULL"),
    )
    op.create_index(
        "ix_watcher_notif_event", "watcher_notifications",
        ["event_id"],
    )

    # ── notification_channels ────────────────────────────────
    op.create_table(
        "notification_channels",
        sa.Column(
            "id", UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(),
            nullable=False, server_default=sa.text("true"),
        ),
        sa.Column(
            "config", JSONB(),
            nullable=False, server_default="{}",
        ),
        sa.Column(
            "priority", sa.Integer(),
            nullable=False, server_default="0",
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
        "uq_notif_channels_tenant_type", "notification_channels",
        ["tenant_id", "channel_type"], unique=True,
    )
    op.create_index(
        "ix_notif_channels_enabled", "notification_channels",
        ["tenant_id", "enabled"],
        postgresql_where=sa.text("enabled = true"),
    )


def downgrade() -> None:
    op.drop_index("ix_notif_channels_enabled")
    op.drop_index("uq_notif_channels_tenant_type")
    op.drop_table("notification_channels")

    op.drop_index("ix_watcher_notif_event")
    op.drop_index("ix_watcher_notif_digest")
    op.drop_index("ix_watcher_notif_pending")
    op.drop_index("ix_watcher_notif_tenant_created")
    op.drop_table("watcher_notifications")

    op.drop_index("ix_tech_radar_tags")
    op.drop_index("ix_tech_radar_tenant_source")
    op.drop_index("ix_tech_radar_tenant_score")
    op.drop_index("ix_tech_radar_tenant_scraped")
    op.drop_index("uq_tech_radar_tenant_url")
    op.drop_table("tech_radar")

    op.drop_index("ix_watcher_runs_failed")
    op.drop_index("ix_watcher_runs_tenant_watcher")
    op.drop_table("watcher_runs")

    op.drop_index("ix_watch_events_run")
    op.drop_index("ix_watch_events_unacked")
    op.drop_index("ix_watch_events_tenant_watcher")
    op.drop_index("ix_watch_events_tenant_severity")
    op.drop_index("ix_watch_events_tenant_created")
    op.drop_table("watch_events")

    op.drop_index("ix_watch_configs_enabled")
    op.drop_index("ix_watch_configs_tenant")
    op.drop_index("uq_watch_configs_tenant_name")
    op.drop_table("watch_configs")

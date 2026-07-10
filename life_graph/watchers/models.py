"""SQLAlchemy 2.0 ORM models for Era 6: Ambient AI watchers.

Six models: WatchConfig, WatchEvent, WatcherRun, TechRadarItem,
WatcherNotification, NotificationChannel.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from life_graph.models.db import Base, _utcnow


class WatchConfig(Base):
    """Configuration for an ambient watcher (schedule, enabled state, failure tracking)."""

    __tablename__ = "watch_configs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    watcher_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    schedule: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("uq_watch_configs_tenant_name", "tenant_id", "watcher_name", unique=True),
        Index("ix_watch_configs_tenant", "tenant_id"),
        Index(
            "ix_watch_configs_enabled", "tenant_id", "enabled",
            postgresql_where="enabled = true",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<WatchConfig(id={self.id!s:.8}, "
            f"watcher={self.watcher_name}, "
            f"enabled={self.enabled})>"
        )


class WatchEvent(Base):
    """An event emitted by a watcher run (critical, important, or info)."""

    __tablename__ = "watch_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    watcher_name: Mapped[str] = mapped_column(Text, nullable=False)
    run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("watcher_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    acknowledged_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Relationships ─────────────────────────────────────────
    notifications: Mapped[list[WatcherNotification]] = relationship(
        "WatcherNotification", back_populates="event", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_watch_events_tenant_created", "tenant_id", "created_at"),
        Index("ix_watch_events_tenant_severity", "tenant_id", "severity", "created_at"),
        Index("ix_watch_events_tenant_watcher", "tenant_id", "watcher_name", "created_at"),
        Index(
            "ix_watch_events_unacked", "tenant_id", "created_at",
            postgresql_where="acknowledged_at IS NULL",
        ),
        Index("ix_watch_events_run", "run_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<WatchEvent(id={self.id!s:.8}, "
            f"severity={self.severity}, "
            f"title={self.title[:30]!r})>"
        )


class WatcherRun(Base):
    """Record of a single watcher execution."""

    __tablename__ = "watcher_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    watcher_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="running")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    events_generated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_watcher_runs_tenant_watcher", "tenant_id", "watcher_name", "created_at"),
        Index(
            "ix_watcher_runs_failed", "tenant_id", "created_at",
            postgresql_where="status = 'failed'",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<WatcherRun(id={self.id!s:.8}, "
            f"watcher={self.watcher_name}, "
            f"status={self.status})>"
        )


class TechRadarItem(Base):
    """A scored tech article from HN, Reddit, or GitHub trending."""

    __tablename__ = "tech_radar"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    source_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    subreddit: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    upvotes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    comments: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, server_default="{}"
    )
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("uq_tech_radar_tenant_url", "tenant_id", "url", unique=True),
        Index("ix_tech_radar_tenant_scraped", "tenant_id", "scraped_at"),
        Index("ix_tech_radar_tenant_score", "tenant_id", "score"),
        Index("ix_tech_radar_tenant_source", "tenant_id", "source", "scraped_at"),
        Index("ix_tech_radar_tags", "tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return (
            f"<TechRadarItem(id={self.id!s:.8}, "
            f"title={self.title[:30]!r}, "
            f"score={self.score})>"
        )


class WatcherNotification(Base):
    """A notification generated from a watch event (delivery tracking)."""

    __tablename__ = "watcher_notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("watch_events.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    recipient: Mapped[str | None] = mapped_column(Text, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    digest_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Relationships ─────────────────────────────────────────
    event: Mapped[WatchEvent] = relationship(
        "WatchEvent", back_populates="notifications"
    )

    __table_args__ = (
        Index("ix_watcher_notif_tenant_created", "tenant_id", "created_at"),
        Index(
            "ix_watcher_notif_pending", "tenant_id", "status",
            postgresql_where="status IN ('pending','queued','failed')",
        ),
        Index(
            "ix_watcher_notif_digest", "digest_id",
            postgresql_where="digest_id IS NOT NULL",
        ),
        Index("ix_watcher_notif_event", "event_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<WatcherNotification(id={self.id!s:.8}, "
            f"channel={self.channel}, "
            f"status={self.status})>"
        )


class NotificationChannel(Base):
    """Configuration for a notification delivery channel per tenant."""

    __tablename__ = "notification_channels"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    channel_type: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    config: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index(
            "uq_notif_channels_tenant_type", "tenant_id", "channel_type",
            unique=True,
        ),
        Index(
            "ix_notif_channels_enabled", "tenant_id", "enabled",
            postgresql_where="enabled = true",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<NotificationChannel(id={self.id!s:.8}, "
            f"type={self.channel_type}, "
            f"enabled={self.enabled})>"
        )

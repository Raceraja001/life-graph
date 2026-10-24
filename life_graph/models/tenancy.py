"""Tenant operations: jobs, usage, budgets, config, webhooks, notifications, push and Telegram.

SQLAlchemy 2.0 ``mapped_column`` models, split out of ``models/db.py`` on
2026-10-25; ``life_graph.models.db`` still re-exports every one of them.
Every table is tenant-scoped (CHARTER invariant 4)."""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.models.base import Base, _utcnow


class JobRun(Base):
    """Record of a background job execution.

    Tracks consolidation and other async tasks for monitoring
    and retry management.
    """

    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )  # queued | running | success | failed
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_job_runs_tenant", "tenant_id", "created_at"),
        Index("ix_job_runs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<JobRun(id={self.id!s:.8}, job={self.job_name}, status={self.status})>"


class TenantUsage(Base):
    """Hourly usage counters per tenant for metering and billing."""

    __tablename__ = "tenant_usage"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    api_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memories_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)

    __table_args__ = (Index("ix_tenant_usage_lookup", "tenant_id", "period_start"),)

    def __repr__(self) -> str:
        return f"<TenantUsage(tenant={self.tenant_id}, period={self.period_start})>"


class BudgetSpend(Base):
    """Month-to-date spend per tenant per category — the Governor's ledger.

    A rolling aggregate (one row per tenant/month/category) so the Governor can
    read month-to-date spend cheaply before authorizing a new spend. See
    ``services/governor.py`` and ``core/budget.py``.
    """

    __tablename__ = "budget_spend"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    period_month: Mapped[datetime] = mapped_column(
        Date, nullable=False, doc="First day of the UTC month this row aggregates."
    )
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    spent_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "period_month", "category", name="uq_budget_spend_key"),
        Index("ix_budget_spend_lookup", "tenant_id", "period_month"),
    )

    def __repr__(self) -> str:
        return (
            f"<BudgetSpend(tenant={self.tenant_id}, month={self.period_month}, "
            f"category={self.category}, spent={self.spent_usd})>"
        )


class TenantConfig(Base):
    """Configuration and lifecycle status for a provisioned tenant."""

    __tablename__ = "tenant_configs"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | deactivated | deleted
    provisioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cold_start_config: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Per-tenant cold start questions/config. Null = use defaults.",
    )
    autonomy_paused: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Kill-switch: when true, AutoFixService._run_action refuses to "
        "execute any autonomous action for this tenant.",
    )
    autonomy_paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (Index("ix_tenant_configs_status", "status"),)

    def __repr__(self) -> str:
        return f"<TenantConfig(tenant={self.tenant_id}, status={self.status})>"


class TenantWebhook(Base):
    """Webhook registration for outbound event notifications per tenant."""

    __tablename__ = "tenant_webhooks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    secret: Mapped[str] = mapped_column(String(256), nullable=False)
    events: Mapped[str] = mapped_column(
        String(500), nullable=False, default="*"
    )  # comma-separated event types or "*" for all
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        Index("ix_tenant_webhooks_tenant", "tenant_id"),
        Index("ix_tenant_webhooks_active", "tenant_id", "active"),
    )

    def __repr__(self) -> str:
        return f"<TenantWebhook(id={self.id!s:.8}, tenant={self.tenant_id}, url={self.url[:30]})>"


class Notification(Base):
    """Priority-routed notification for kernel events.

    Notifications are created by the notification engine
    when events fire (task failures, schedule disables, etc.).
    Supports multiple delivery channels: terminal, email, webhook.
    """

    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="legacy",
    )
    priority: Mapped[str] = mapped_column(
        String(10),
        nullable=False,
        default="info",
    )
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="terminal",
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    body: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default="{}",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    is_delivered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    delivery_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    source_type: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )

    __table_args__ = (
        Index(
            "ix_notifications_tenant",
            "tenant_id",
            "created_at",
        ),
        Index(
            "ix_notifications_unread",
            "tenant_id",
            "is_read",
            "created_at",
        ),
        Index(
            "ix_notifications_priority",
            "tenant_id",
            "priority",
            "created_at",
        ),
        Index(
            "ix_notifications_pending",
            "is_delivered",
            "priority",
            "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id!s:.8}, priority={self.priority}, title={self.title[:30]})>"
        )


class PushSubscription(Base):
    """A browser/device Web Push subscription for a tenant."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    endpoint: Mapped[str] = mapped_column(Text, nullable=False)
    p256dh: Mapped[str] = mapped_column(Text, nullable=False)
    auth: Mapped[str] = mapped_column(Text, nullable=False)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("uq_push_sub_endpoint", "endpoint", unique=True),
        Index("ix_push_sub_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return f"<PushSubscription(id={self.id!s:.8}, tenant={self.tenant_id})>"


# ── Telegram Bridge Models ─────────────────────────────────────────
class TelegramBinding(Base):
    """Links one Telegram chat to one tenant.

    The Bot API gives us a ``chat_id`` and no authentication of its own, so this
    table is where a message acquires a tenant. Code that handles an inbound
    update must look the chat up here and drop the message when there is no
    active binding — there is no default tenant to fall back to.
    """

    __tablename__ = "telegram_bindings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        doc="Telegram chat id. BigInteger because supergroup ids exceed int4.",
    )
    chat_type: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="private",
        doc="Telegram chat type: private, group, supergroup, channel",
    )
    username: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="@handle at bind time, for display only"
    )
    active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        doc="Revoking sets this False rather than deleting, keeping the audit trail",
    )
    bound_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        # Partial unique: one active binding per chat, so a chat can never be
        # bound to two tenants at once. Enforced here rather than in code
        # because concurrent pairing attempts would race a SELECT-then-INSERT.
        Index("ix_telegram_bindings_chat", "chat_id", unique=True, postgresql_where=text("active")),
        Index("ix_telegram_bindings_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TelegramBinding(chat={self.chat_id}, tenant={self.tenant_id}, active={self.active})>"
        )


class TelegramPairingCode(Base):
    """A short-lived, single-use code that binds a chat to a tenant.

    The code is the only secret between a stranger and a write into someone
    else's memory, so it is short-lived, single-use (``used_at``), and issued
    only to an already-authenticated API caller.
    """

    __tablename__ = "telegram_pairing_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, doc="Set on redemption; a set value means spent"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (Index("ix_telegram_pairing_expires", "expires_at"),)

    def __repr__(self) -> str:
        return f"<TelegramPairingCode(tenant={self.tenant_id}, used={self.used_at is not None})>"

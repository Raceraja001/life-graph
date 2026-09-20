"""Connector accounts and the item index (migrations 039, 040)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.config import settings
from life_graph.models.db import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class ConnectorAccount(Base):
    """One account of one connector (a mailbox, a calendar feed).

    ``settings`` holds non-secret connection details (host, username, the
    user's own addresses). The credential is never here: it lives in a 0600
    file keyed by this row's id (``connectors/secrets.py``).
    """

    __tablename__ = "connector_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    connector: Mapped[str] = mapped_column(String(64), nullable=False)
    account_key: Mapped[str] = mapped_column(String(128), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    auth_method: Mapped[str] = mapped_column(String(16), nullable=False)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # standard | local_only — see connectors/exposure.py
    exposure: Mapped[str] = mapped_column(String(16), nullable=False, default="standard")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sync_interval_min: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    cursor: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # never_synced | ok | error | reauth_needed
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="never_synced")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "connector", "account_key", name="uq_connector_account_key"),
    )


class ConnectorItem(Base):
    """One indexed event, message or contact. Bodies are never stored.

    ``local_detail`` (an event's description, notes, meeting links) is shown to
    local models only. ``summary``/``category`` for mail are written by the
    local model; ``summary_state`` is ``pending`` until that has run.
    """

    __tablename__ = "connector_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("connector_accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    external_id: Mapped[str] = mapped_column(String(512), nullable=False)
    thread_key: Mapped[str | None] = mapped_column(String(512))
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    sender_name: Mapped[str | None] = mapped_column(Text)
    sender_addr: Mapped[str | None] = mapped_column(Text)
    to_me: Mapped[bool | None] = mapped_column(Boolean)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    location: Mapped[str | None] = mapped_column(Text)
    attendees: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # People the item involves (lower-cased addresses, never the user's own).
    emails: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(16))
    summary_state: Mapped[str] = mapped_column(String(16), nullable=False, default="none")
    flags: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    local_detail: Mapped[str | None] = mapped_column(Text)
    trust_tier: Mapped[str] = mapped_column(String(24), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(settings.embedding_dimension))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("account_id", "external_id", name="uq_connector_item_external"),
        Index("ix_connector_items_tenant_kind_occurred", "tenant_id", "kind", "occurred_at"),
        Index("ix_connector_items_tenant_kind_starts", "tenant_id", "kind", "starts_at"),
        Index("ix_connector_items_thread", "account_id", "thread_key"),
        Index("ix_connector_items_emails", "emails", postgresql_using="gin"),
    )

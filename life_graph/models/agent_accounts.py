"""Agent accounts: several named logins per coding CLI, and their plan limits.

An *account* is one way a driver CLI (claude_code, codex, gemini) signs in:
the owner's subscription login kept in a home directory life-graph manages
(the CLI writes its own login there; nothing here reads it), an API key held
in the vault, or a cloud project (Vertex). A driver runs a dispatch on one
account by pointing the CLI at that home (``CLAUDE_CONFIG_DIR`` /
``CODEX_HOME`` / ``GEMINI_CLI_HOME``) and, for an API key, injecting the key
from the vault for that one process (services/agent_accounts).

What a row never holds: a credential (``secret_ref`` is the vault row's id;
the ciphertext lives in ``vault_secrets``) or a raw identity (only a masked
form such as ``ra***@g***.com`` and a keyed hash used to refuse duplicates).

Migration 064 creates both tables. Tenant-scoped (CHARTER invariant 4).
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.models.base import Base, _utcnow


class AgentAccount(Base):
    """One named login a driver CLI can run on."""

    __tablename__ = "agent_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # claude_code | codex | gemini | opencode (validated in services, not an
    # enum in the schema: a new driver needs no migration).
    driver: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(60), nullable=False)
    # subscription | api_key | vertex
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    # The CLI's own config/login home, under driver_accounts_home_root. Set by
    # the server at creation, never by a client.
    home_dir: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # The vault_secrets row holding this account's API key (api_key kind).
    secret_ref: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    secret_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    identity_masked: Mapped[str | None] = mapped_column(String(120), nullable=True)
    # HMAC-SHA256 of the normalized identity, keyed from the vault key.
    identity_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Pool order: lower runs first.
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    cooldown_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Scrubbed and clipped (drivers/cli_failure.failure_message).
    last_error: Mapped[str | None] = mapped_column(String(200), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Non-secret settings: vertex project/region, a model override.
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "driver", "name", name="uq_agent_accounts_name"),
        Index("ix_agent_accounts_pool", "tenant_id", "driver", "priority"),
        Index(
            "uq_agent_accounts_identity",
            "tenant_id",
            "driver",
            "identity_hash",
            unique=True,
            postgresql_where=text("identity_hash IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<AgentAccount(id={self.id!s:.8}, driver={self.driver}, name={self.name!r})>"


class AgentAccountLimit(Base):
    """The latest reading of one plan-limit window of one account.

    One row per (account, window); a new reading replaces the old one.
    ``window`` is ``five_hour`` / ``seven_day`` / ``seven_day_opus`` /
    ``monthly`` when known, else the CLI's slot name (``primary``).
    """

    __tablename__ = "agent_account_limits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_accounts.id", ondelete="CASCADE"), nullable=False
    )
    window: Mapped[str] = mapped_column(String(32), nullable=False)
    used_percent: Mapped[float] = mapped_column(Float, nullable=False)
    window_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resets_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # allowed | warning | rejected, when the CLI says
    status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # run (a dispatch reported it) | probe (codex app-server)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default="run")
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("account_id", "window", name="uq_agent_account_limits_window"),
        Index("ix_agent_account_limits_tenant", "tenant_id", "account_id"),
    )

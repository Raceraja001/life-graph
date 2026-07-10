"""SQLAlchemy 2.0 ORM models for the Life Graph memory system.

All models use mapped_column style with UUID primary keys,
JSONB for schema-less properties, and pgvector for embeddings.
Multi-tenant: every model has a `tenant_id` column.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer,
    Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    """Return the current UTC timestamp (timezone-aware)."""
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base for all Life Graph models."""

    pass


class Memory(Base):
    """A single memory unit — facts, preferences, decisions, lessons, or observations.

    Memories are the core data atom of the Life Graph. They support
    brain-inspired features: importance tiers, decay, temporal validity,
    trust scoring, supersession chains, and vector embeddings.
    """

    __tablename__ = "memories"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Content ───────────────────────────────────────────────
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # ── Scoring ───────────────────────────────────────────────
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    importance_tier: Mapped[str] = mapped_column(String, nullable=False, default="normal")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # ── Source & Trust ────────────────────────────────────────
    source_type: Mapped[str] = mapped_column(String, nullable=False, default="inferred")
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    trust_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    valid_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Access & Decay ────────────────────────────────────────
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    decay_rate: Mapped[float] = mapped_column(Float, nullable=False, default=0.1)

    # ── Reinforcement (Confidence Decay) ──────────────────────
    last_reinforced: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
        doc="Last time user confirmed this memory is still accurate",
    )
    reinforced_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        doc="Number of times user confirmed this memory",
    )

    # ── Extraction Provenance ─────────────────────────────────
    extraction_tier: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        doc="Which extraction tier created this: regex, spacy, llm, manual",
    )
    extraction_confidence: Mapped[float | None] = mapped_column(
        Float, nullable=True,
        doc="Confidence score from the extraction pipeline (0.0-1.0)",
    )

    # ── Impact Scoring (Feature 5) ────────────────────────────
    impact_score: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5,
        doc="Learned usefulness from session outcome feedback (0.0-1.0)",
    )
    impact_confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0,
        doc="Confidence in impact_score (grows with more data points)",
    )

    # ── Supersession Chain ────────────────────────────────────
    supersedes: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Tenant ─────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )

    # ── Status & Owner ────────────────────────────────────────
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    owner: Mapped[str] = mapped_column(String, nullable=False, default="default")

    # ── Deduplication ─────────────────────────────────────────
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="SHA-256 of normalized content for dedup"
    )

    # ── Capture Spine ─────────────────────────────────────────
    capture_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        doc="Links this memory to the capture event that produced it",
    )

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )
    embedding_model: Mapped[str] = mapped_column(
        String, nullable=False, default="all-mpnet-base-v2"
    )

    # ── Relationships ─────────────────────────────────────────
    sessions: Mapped[list[MemorySession]] = relationship(
        "MemorySession", back_populates="memory", cascade="all, delete-orphan"
    )
    supersedes_memory: Mapped[Memory | None] = relationship(
        "Memory", foreign_keys=[supersedes], remote_side=[id], uselist=False
    )
    superseded_by_memory: Mapped[Memory | None] = relationship(
        "Memory", foreign_keys=[superseded_by], remote_side=[id], uselist=False
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_memories_status", "status"),
        Index("ix_memories_importance", "importance"),
        Index("ix_memories_created_at", "created_at"),
        Index("ix_memories_owner", "owner"),
        Index("ix_memories_tags", "tags", postgresql_using="gin"),
        Index("ix_memories_properties", "properties", postgresql_using="gin"),
        Index("ix_memories_tenant_created", "tenant_id", "created_at"),
        Index("ix_memories_tenant_status", "tenant_id", "status"),
        Index("ix_memories_content_hash", "tenant_id", "content_hash"),
    )

    def __repr__(self) -> str:
        return f"<Memory(id={self.id!s:.8}, content={self.content[:40]!r})>"


class Session(Base):
    """A conversation or interaction session.

    Sessions group memories created/accessed during one interaction
    and capture context for retrieval during future sessions.
    """

    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    memories_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memories_accessed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
        doc="Session result: success, failure, or neutral",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────
    memory_links: Mapped[list[MemorySession]] = relationship(
        "MemorySession", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sessions_started_at", "started_at"),
        Index("ix_sessions_tenant_started", "tenant_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<Session(id={self.id!s:.8}, started_at={self.started_at})>"


class Intention(Base):
    """A prospective memory — something the system should remember to do.

    Intentions model the brain's prospective memory: actions triggered
    by events, conditions, or scheduled times.
    """

    __tablename__ = "intentions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String, nullable=False, default="event")
    trigger_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    context_match: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[str] = mapped_column(String, nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    triggered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Foreign Keys ──────────────────────────────────────────
    source_session: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_memory: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )

    __table_args__ = (
        Index("ix_intentions_status", "status"),
        Index("ix_intentions_trigger_type", "trigger_type"),
        Index("ix_intentions_trigger_time", "trigger_time"),
        Index("ix_intentions_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<Intention(id={self.id!s:.8}, content={self.content[:40]!r})>"


class KnowledgeGap(Base):
    """A recorded gap in the system's knowledge — metamemory.

    Tracks topics the system has been asked about but couldn't answer,
    enabling proactive gap-filling and prioritized learning.
    """

    __tablename__ = "knowledge_gaps"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    query_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    first_asked: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    last_asked: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="SET NULL"),
        nullable=True,
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )

    __table_args__ = (
        Index("ix_knowledge_gaps_resolved", "resolved"),
        Index("ix_knowledge_gaps_query_count", "query_count"),
        Index("ix_knowledge_gaps_tenant", "tenant_id", "resolved"),
    )

    def __repr__(self) -> str:
        return f"<KnowledgeGap(id={self.id!s:.8}, topic={self.topic[:40]!r})>"


class MemorySession(Base):
    """Association table linking memories to the sessions in which they were created or accessed."""

    __tablename__ = "memory_sessions"

    memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="created",
        doc="Whether memory was 'created' or 'recalled' in this session",
    )
    was_useful: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
        doc="Per-memory usefulness feedback (v2)",
    )

    # ── Relationships ─────────────────────────────────────────
    memory: Mapped[Memory] = relationship("Memory", back_populates="sessions")
    session: Mapped[Session] = relationship("Session", back_populates="memory_links")

    def __repr__(self) -> str:
        return f"<MemorySession(memory={self.memory_id!s:.8}, session={self.session_id!s:.8})>"


class MemoryLink(Base):
    """Typed bidirectional link between two memories (Zettelkasten-style).

    Supports relationship types: BECAUSE, EVIDENCED_BY, RELATED_TO,
    CONTRADICTS, SUPERSEDES, LEADS_TO.
    """

    __tablename__ = "memory_links"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("memories.id", ondelete="CASCADE"),
        nullable=False,
    )
    link_type: Mapped[str] = mapped_column(String(30), nullable=False)
    strength: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )

    __table_args__ = (
        Index("ix_memory_links_source", "source_memory_id"),
        Index("ix_memory_links_target", "target_memory_id"),
        Index("ix_memory_links_type", "link_type"),
        Index("ix_memory_links_tenant", "tenant_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<MemoryLink(id={self.id!s:.8}, "
            f"{self.source_memory_id!s:.8} -{self.link_type}-> "
            f"{self.target_memory_id!s:.8})>"
        )


class JobRun(Base):
    """Record of a background job execution.

    Tracks consolidation and other async tasks for monitoring
    and retry management.
    """

    __tablename__ = "job_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    job_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )  # queued | running | success | failed
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    api_calls: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memories_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    llm_cost_usd: Mapped[float] = mapped_column(
        Numeric(10, 6), nullable=False, default=0
    )

    __table_args__ = (
        Index("ix_tenant_usage_lookup", "tenant_id", "period_start"),
    )

    def __repr__(self) -> str:
        return f"<TenantUsage(tenant={self.tenant_id}, period={self.period_start})>"


class TenantConfig(Base):
    """Configuration and lifecycle status for a provisioned tenant."""

    __tablename__ = "tenant_configs"

    tenant_id: Mapped[str] = mapped_column(
        String(64), primary_key=True
    )
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active | deactivated | deleted
    provisioned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cold_start_config: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True, default=None,
        comment="Per-tenant cold start questions/config. Null = use defaults.",
    )

    __table_args__ = (
        Index("ix_tenant_configs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<TenantConfig(tenant={self.tenant_id}, status={self.status})>"


class TenantWebhook(Base):
    """Webhook registration for outbound event notifications per tenant."""

    __tablename__ = "tenant_webhooks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False
    )
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


class Procedure(Base):
    """A learned behavioral pattern or strategy.

    Procedures capture recurring workflows distilled from multiple
    sessions.  They store a trigger condition, ordered steps, and
    performance statistics.
    """

    __tablename__ = "procedures"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    trigger: Mapped[str] = mapped_column(Text, nullable=False)
    steps: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    learned_from: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    times_applied: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )

    @property
    def success_rate(self) -> float:
        """Calculate success rate from applications."""
        if self.times_applied == 0:
            return 0.0
        return self.success_count / self.times_applied

    __table_args__ = (
        Index("ix_procedures_status", "status"),
        Index("ix_procedures_tenant", "tenant_id"),
        Index("ix_procedures_confidence", "confidence"),
    )

    def __repr__(self) -> str:
        return f"<Procedure(id={self.id!s:.8}, trigger={self.trigger[:40]!r})>"


# ── OS Kernel Models ──────────────────────────────────────────


class AgentSession(Base):
    """Tracks routing decisions and conversation chains across agent handoffs."""

    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    classified_intent: Mapped[str | None] = mapped_column(
        String(30), nullable=True
    )
    classification_conf: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.0
    )
    routed_to: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    handoff_chain: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    total_duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    total_cost_usd: Mapped[float] = mapped_column(
        Numeric(10, 6), nullable=False, default=0
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active|completed|failed|abandoned
    context: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    memory_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_agent_sessions_tenant", "tenant_id", "created_at"),
        Index(
            "ix_agent_sessions_intent",
            "tenant_id",
            "classified_intent",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentSession(id={self.id!s:.8}, "
            f"intent={self.classified_intent}, "
            f"status={self.status})>"
        )


class AgentPersona(Base):
    """Database-driven agent configuration — personas define agent behavior without code changes."""

    __tablename__ = "agent_personas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gemini/gemini-2.5-flash"
    )
    temperature: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, default=4096
    )
    allowed_tools: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    intent_tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    icon: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    use_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    # ── Agent Driver Columns ──────────────────────────────────
    driver: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        doc="Default driver for this persona (local, claude_code, codex, etc.)",
    )
    verifier_chain: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]",
        doc="Ordered list of verifier names to run after task completion",
    )
    context_profile: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}",
        doc="Context packet configuration: which sections to include, token budgets",
    )
    task_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}",
        doc="Task types this persona can handle",
    )

    __table_args__ = (
        Index(
            "ix_agent_personas_name",
            "tenant_id",
            "name",
            unique=True,
        ),
        Index("ix_agent_personas_tenant", "tenant_id", "is_active"),
        Index(
            "ix_agent_personas_intent",
            "intent_tags",
            postgresql_using="gin",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentPersona(id={self.id!s:.8}, "
            f"name={self.name}, "
            f"builtin={self.is_builtin})>"
        )


class AgentTask(Base):
    """An agent task — like an OS process.

    Tracks the full lifecycle of a spawned agent execution.
    """

    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )
    task_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_name: Mapped[str] = mapped_column(
        String(100), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )  # queued|running|completed|failed|cancelled|timeout
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="normal"
    )  # low|normal|high|critical
    input: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    result: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    token_usage: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    model_used: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=300
    )
    retry_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=2
    )
    parent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # ── Era 7 additions ──
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(
        String(30), nullable=False, default="general"
    )
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_agent: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    created_by_agent: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    root_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    depth: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    on_child_failure: Mapped[str] = mapped_column(
        String(20), nullable=False, default="continue"
    )
    status_history: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    workflow_step_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String(50)), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    __table_args__ = (
        Index(
            "ix_agent_tasks_tenant_status", "tenant_id", "status"
        ),
        Index(
            "ix_agent_tasks_tenant_created",
            "tenant_id",
            "created_at",
        ),
        Index("ix_agent_tasks_agent", "tenant_id", "agent_name"),
        Index("ix_agent_tasks_session", "session_id"),
        Index("ix_agent_tasks_parent", "parent_task_id"),
        Index("ix_agent_tasks_assigned", "tenant_id", "assigned_agent", "status"),
        Index("ix_agent_tasks_root", "root_task_id"),
        Index("ix_agent_tasks_project", "tenant_id", "project_id"),
        Index("ix_agent_tasks_workflow", "workflow_run_id"),
        Index("ix_agent_tasks_created_desc", "tenant_id", "created_at"),
        Index("ix_agent_tasks_properties", "properties", postgresql_using="gin"),
        Index("ix_agent_tasks_tags", "tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentTask(id={self.id!s:.8}, "
            f"agent={self.agent_name}, "
            f"status={self.status})>"
        )


class ScheduledJob(Base):
    """Persistent cron job configuration.

    Each scheduled job fires on a cron schedule and spawns
    an agent task via the ProcessManager. Tracks run history,
    consecutive failures, and auto-disables after 3 failures.
    """

    __tablename__ = "scheduled_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy",
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100), nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(
        String(100), nullable=False,
    )
    input: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    run_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_run_status: Mapped[str | None] = mapped_column(
        String(20), nullable=True,
    )
    last_run_task_id: Mapped[uuid.UUID | None] = (
        mapped_column(
            UUID(as_uuid=True),
            ForeignKey(
                "agent_tasks.id", ondelete="SET NULL",
            ),
            nullable=True,
        )
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3,
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=600,
    )
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    __table_args__ = (
        Index(
            "ix_scheduled_jobs_name",
            "tenant_id",
            "name",
            unique=True,
        ),
        Index(
            "ix_scheduled_jobs_tenant",
            "tenant_id",
            "is_active",
        ),
        Index(
            "ix_scheduled_jobs_next_run",
            "next_run_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<ScheduledJob(id={self.id!s:.8}, "
            f"name={self.name}, "
            f"cron={self.cron_expression})>"
        )


class Project(Base):
    """Registered codebase for project-aware agent context.

    Stores project metadata, git info, dependency counts,
    and scan results. Used by the Chief Router to inject
    project context into agent system prompts.
    """

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy",
    )
    name: Mapped[str] = mapped_column(
        String(200), nullable=False,
    )
    path: Mapped[str] = mapped_column(
        Text, nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    git_url: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    git_branch: Mapped[str | None] = mapped_column(
        String(200), nullable=True,
    )
    language: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )
    framework: Mapped[str | None] = mapped_column(
        String(100), nullable=True,
    )
    dependency_file: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    dependency_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    file_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    recent_commits: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]",
    )
    scan_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}",
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    __table_args__ = (
        Index(
            "ix_projects_name",
            "tenant_id", "name",
            unique=True,
        ),
        Index(
            "ix_projects_tenant",
            "tenant_id", "is_active",
        ),
        Index(
            "ix_projects_language",
            "tenant_id", "language",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Project(id={self.id!s:.8}, "
            f"name={self.name}, "
            f"lang={self.language})>"
        )


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
        String(64), nullable=False, default="legacy",
    )
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="info",
    )
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False, default="terminal",
    )
    title: Mapped[str] = mapped_column(
        String(500), nullable=False,
    )
    body: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    extra_metadata: Mapped[dict] = mapped_column(
        "metadata",
        JSONB, nullable=False, server_default="{}",
    )
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    is_delivered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    delivery_error: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    source_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
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
            "tenant_id", "is_read", "created_at",
        ),
        Index(
            "ix_notifications_priority",
            "tenant_id", "priority", "created_at",
        ),
        Index(
            "ix_notifications_pending",
            "is_delivered", "priority", "created_at",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Notification(id={self.id!s:.8}, "
            f"priority={self.priority}, "
            f"title={self.title[:30]})>"
        )


# ── Era 4: Personal AI ──────────────────────────────────────────────────────


class Preference(Base):
    """A user preference — opinions, likes/dislikes, technology choices, etc.

    Preferences are the evolved form of identity memories, with proper
    evidence tracking, confidence history, and semantic search.
    """

    __tablename__ = "preferences"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )

    # ── Content ───────────────────────────────────────────────
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    choice: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Confidence ────────────────────────────────────────────
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    confidence_history: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # ── Source ────────────────────────────────────────────────
    source: Mapped[str] = mapped_column(
        String(20), nullable=False, default="explicit"
    )
    source_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Categorization ────────────────────────────────────────
    tags: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True
    )
    category: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # ── Validation ────────────────────────────────────────────
    last_validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    validated_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    last_challenged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )
    embedding_model: Mapped[str] = mapped_column(
        String(50), nullable=False, default="all-mpnet-base-v2"
    )

    # ── Status & Timestamps ───────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
        onupdate=_utcnow,
    )

    # ── Relationships ─────────────────────────────────────────
    evidence_items: Mapped[list["Evidence"]] = relationship(
        "Evidence", back_populates="preference",
        cascade="all, delete-orphan",
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_pref_tenant_status", "tenant_id", "status"),
        Index("ix_pref_tenant_topic", "tenant_id", "topic"),
        Index("ix_pref_tenant_category", "tenant_id", "category"),
        Index("ix_pref_confidence", "confidence"),
        Index("ix_pref_last_validated", "last_validated_at"),
        Index("ix_pref_tags", "tags", postgresql_using="gin"),
        Index("ix_pref_properties", "properties", postgresql_using="gin"),
        Index("ix_pref_source", "source"),
    )

    def __repr__(self) -> str:
        return f"<Preference(id={self.id!s:.8}, topic={self.topic[:30]!r})>"


class Evidence(Base):
    """A piece of evidence supporting or contradicting a preference.

    Evidence comes from benchmarks, papers, articles, HN discussions,
    blog posts, GitHub trends, Reddit threads, or AI opinions.
    """

    __tablename__ = "evidence"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )

    # ── FK to Preference ──────────────────────────────────────
    preference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("preferences.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Source ────────────────────────────────────────────────
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Content ───────────────────────────────────────────────
    stance: Mapped[str] = mapped_column(
        String(10), nullable=False, default="supports"
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Scoring ───────────────────────────────────────────────
    credibility: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )
    weight: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.0
    )

    # ── Metadata ──────────────────────────────────────────────
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )
    embedding_model: Mapped[str] = mapped_column(
        String(50), nullable=False, default="all-mpnet-base-v2"
    )

    # ── Status & Timestamps ───────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Relationships ─────────────────────────────────────────
    preference: Mapped["Preference"] = relationship(
        "Preference", back_populates="evidence_items"
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_evidence_pref_stance", "preference_id", "stance"),
        Index("ix_evidence_tenant_status", "tenant_id", "status"),
        Index("ix_evidence_source_type", "source_type"),
        Index("ix_evidence_stance", "stance"),
    )

    def __repr__(self) -> str:
        return (
            f"<Evidence(id={self.id!s:.8}, "
            f"stance={self.stance}, source={self.source_type})>"
        )


class AdvisorSession(Base):
    """A Q&A session with the personal advisor.

    Tracks questions asked, answers given, and what evidence/preferences
    were used to form the answer.
    """

    __tablename__ = "advisor_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources_used: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    preferences_cited: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.5
    )
    consensus_score: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    answered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_advisor_tenant_created", "tenant_id", "created_at"),
        Index("ix_advisor_consensus", "consensus_score"),
        Index("ix_advisor_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<AdvisorSession(id={self.id!s:.8}, status={self.status})>"


class ResearchRun(Base):
    """A research run — searching external sources for evidence.

    Tracks what was searched, what was found, and which preferences
    were affected by the new evidence.
    """

    __tablename__ = "research_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(
        String(64), nullable=False, default="legacy"
    )
    query: Mapped[str] = mapped_column(Text, nullable=False)
    sources_searched: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    evidence_found: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    evidence_added: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    preferences_affected: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_research_tenant_started", "tenant_id", "started_at"),
        Index("ix_research_tenant_status", "tenant_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<ResearchRun(id={self.id!s:.8}, status={self.status})>"


# ── Era 7: Agent Networks ──────────────────────────────────────────────────


class AgentMessage(Base):
    """Inter-agent message — supports threaded conversations and task requests."""

    __tablename__ = "agent_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    sender_agent: Mapped[str] = mapped_column(String(64), nullable=False)
    recipient_agent: Mapped[str] = mapped_column(String(64), nullable=False)
    thread_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_messages.id", ondelete="SET NULL"), nullable=True,
    )
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    attachments: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unread")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    __table_args__ = (
        Index("ix_agent_messages_inbox", "tenant_id", "recipient_agent", "status"),
        Index("ix_agent_messages_outbox", "tenant_id", "sender_agent"),
        Index("ix_agent_messages_thread", "thread_id"),
        Index("ix_agent_messages_task", "task_id"),
        Index("ix_agent_messages_type", "tenant_id", "message_type"),
    )

    def __repr__(self) -> str:
        return f"<AgentMessage(id={self.id!s:.8}, {self.sender_agent}→{self.recipient_agent})>"


class CrossSystemSync(Base):
    """Record of a cross-system data sync operation."""

    __tablename__ = "cross_system_syncs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    direction: Mapped[str] = mapped_column(String(20), nullable=False)
    sync_type: Mapped[str] = mapped_column(String(40), nullable=False)
    target_system: Mapped[str] = mapped_column(String(40), nullable=False)
    endpoint_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    records_sent: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_synced: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sync_duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    response_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_css_tenant_status", "tenant_id", "status"),
        Index("ix_css_tenant_target", "tenant_id", "target_system"),
    )

    def __repr__(self) -> str:
        return f"<CrossSystemSync(id={self.id!s:.8}, {self.direction} {self.sync_type}→{self.target_system})>"


class Workflow(Base):
    """A reusable workflow definition — sequence of agent steps."""

    __tablename__ = "workflows"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)

    # Relationships
    steps: Mapped[list["WorkflowStep"]] = relationship("WorkflowStep", back_populates="workflow", cascade="all, delete-orphan")
    runs: Mapped[list["WorkflowRun"]] = relationship("WorkflowRun", back_populates="workflow", cascade="all, delete-orphan")

    __table_args__ = (
        Index("uq_workflows_tenant_name", "tenant_id", "name", unique=True),
        Index("ix_workflows_tenant_active", "tenant_id", "is_active"),
    )

    def __repr__(self) -> str:
        return f"<Workflow(id={self.id!s:.8}, name={self.name})>"


class WorkflowStep(Base):
    """A single step within a workflow definition."""

    __tablename__ = "workflow_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False,
    )
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    assigned_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=3600)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    depends_on: Mapped[list[str] | None] = mapped_column(ARRAY(String(64)), nullable=True)
    condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    on_failure: Mapped[str] = mapped_column(String(20), nullable=False, default="abort")
    on_timeout: Mapped[str] = mapped_column(String(20), nullable=False, default="abort")
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="steps")

    __table_args__ = (
        Index("uq_wfs_workflow_key", "workflow_id", "step_key", unique=True),
        Index("ix_wfs_workflow_order", "workflow_id", "step_order"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowStep(id={self.id!s:.8}, key={self.step_key})>"


class WorkflowRun(Base):
    """An execution instance of a workflow."""

    __tablename__ = "workflow_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    triggered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow: Mapped["Workflow"] = relationship("Workflow", back_populates="runs")
    step_runs: Mapped[list["WorkflowStepRun"]] = relationship("WorkflowStepRun", back_populates="run", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_wfr_tenant_status", "tenant_id", "status"),
        Index("ix_wfr_workflow", "workflow_id"),
        Index("ix_wfr_tenant_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowRun(id={self.id!s:.8}, status={self.status})>"


class WorkflowStepRun(Base):
    """Execution instance of a single workflow step."""

    __tablename__ = "workflow_step_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workflow_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_runs.id", ondelete="CASCADE"), nullable=False,
    )
    workflow_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True,
    )
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    run: Mapped["WorkflowRun"] = relationship("WorkflowRun", back_populates="step_runs")

    __table_args__ = (
        Index("uq_wfsr_run_step", "workflow_run_id", "workflow_step_id", unique=True),
        Index("ix_wfsr_step", "workflow_step_id"),
        Index("ix_wfsr_task", "agent_task_id"),
    )

    def __repr__(self) -> str:
        return f"<WorkflowStepRun(id={self.id!s:.8}, status={self.status})>"


class SharedContext(Base):
    """Shared context between agents — findings, decisions, artifacts."""

    __tablename__ = "shared_context"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="SET NULL"), nullable=True,
    )
    source_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, default="finding")
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(768), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow)
    last_accessed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    __table_args__ = (
        Index("ix_sc_tenant_project", "tenant_id", "project_id"),
        Index("ix_sc_task", "source_task_id"),
        Index("ix_sc_agent", "tenant_id", "source_agent"),
        Index("ix_sc_type", "tenant_id", "content_type"),
        Index("ix_sc_hash", "tenant_id", "content_hash"),
        Index("ix_sc_tags", "tags", postgresql_using="gin"),
    )

    def __repr__(self) -> str:
        return f"<SharedContext(id={self.id!s:.8}, title={self.title[:30]!r})>"


class CaptureEvent(Base):
    """A raw capture event — every input to the system, regardless of surface.

    Capture events are the entry point of the Capture Spine. They track
    what came in, from where, and whether it has been processed into
    memories, decisions, or procedures.
    """

    __tablename__ = "capture_events"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Source ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    surface: Mapped[str] = mapped_column(
        String(32), nullable=False,
        doc="Where this came from: orchestrator, mcp, cli, voice, tool, watcher, git",
    )
    modality: Mapped[str] = mapped_column(
        String(16), nullable=False, default="text",
        doc="Input modality: text, voice, image, structured",
    )

    # ── Content ───────────────────────────────────────────────
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64), nullable=False,
        doc="SHA-256 hash of content for dedup",
    )

    # ── Processing ────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="received",
        doc="Processing status: received, processed, duplicate, failed",
    )
    yield_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
        doc="Number of memories/artifacts produced from this event",
    )

    # ── Timestamps ────────────────────────────────────────────
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        doc="When the event actually occurred (may differ from created_at)",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Extension ─────────────────────────────────────────────
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_ce_tenant_occurred", "tenant_id", "occurred_at"),
        Index("ix_ce_tenant_surface", "tenant_id", "surface"),
        Index("ix_ce_tenant_hash", "tenant_id", "content_hash"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return f"<CaptureEvent(id={self.id!s:.8}, surface={self.surface}, status={self.status})>"


class Correction(Base):
    """A user correction — edit, override, reject, or approve.

    Corrections feed the self-improving loop: they teach the system
    what the user actually meant vs. what was extracted or inferred.
    """

    __tablename__ = "corrections"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenant & Source ───────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    capture_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_graph.capture_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Correction Detail ─────────────────────────────────────
    kind: Mapped[str] = mapped_column(
        String(16), nullable=False,
        doc="Correction type: edit, override, reject, approve",
    )
    original: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    domain_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}",
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_cor_tenant_created", "tenant_id", "created_at"),
        Index("ix_cor_tenant_kind", "tenant_id", "kind"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return f"<Correction(id={self.id!s:.8}, kind={self.kind})>"


class InterviewQuestion(Base):
    """A question the system wants to ask the user proactively.

    Questions are generated from unresolved outcomes, knowledge gaps,
    preference drift, or periodic reflection prompts.
    """

    __tablename__ = "interview_questions"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenant & Content ──────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Origin ────────────────────────────────────────────────
    origin: Mapped[str] = mapped_column(
        String(32), nullable=False,
        doc="Why this question was generated: outcome_resolution, knowledge_gap, drift, reflection",
    )
    origin_ref: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # ── Priority & Status ─────────────────────────────────────
    priority: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending",
        doc="Lifecycle: pending, asked, answered, skipped, expired",
    )

    # ── Answer ────────────────────────────────────────────────
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_capture_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_graph.capture_events.id", ondelete="SET NULL"),
        nullable=True,
    )
    asked_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Timestamps ────────────────────────────────────────────
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_iq_tenant_status_priority", "tenant_id", "status", "priority"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return f"<InterviewQuestion(id={self.id!s:.8}, status={self.status})>"


# ── Judgment Engine Models ─────────────────────────────────────────


class Decision(Base):
    """A tracked decision — explicit or detected from conversation.

    Decisions are the core atom of the Judgment Engine. They support
    supersession chains, domain tagging, importance scoring, and
    vector embeddings for semantic retrieval.
    """

    __tablename__ = "decisions"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenant ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Content ───────────────────────────────────────────────
    title: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    chosen_option: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Status & Source ───────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="candidate",
        doc="Lifecycle: candidate, decided, reviewed, superseded, discarded",
    )
    source: Mapped[str | None] = mapped_column(
        String(16), nullable=True,
        doc="Origin: conversation, explicit, challenge",
    )

    # ── Classification ────────────────────────────────────────
    domain_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}",
    )
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )

    # ── References ────────────────────────────────────────────
    capture_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        doc="Links this decision to the capture event that produced it",
    )
    challenge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
        doc="Links to a challenge that prompted this decision",
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_graph.decisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_decisions_tenant_created", "tenant_id", "created_at"),
        Index("ix_decisions_tenant_status", "tenant_id", "status"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return f"<Decision(id={self.id!s:.8}, title={self.title[:40]!r}, status={self.status})>"


class Prediction(Base):
    """A falsifiable prediction attached to a decision or standalone.

    Predictions track confidence, resolution criteria, and outcomes
    for calibration scoring.
    """

    __tablename__ = "predictions"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenant ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Decision Link ─────────────────────────────────────────
    decision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_graph.decisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Content ───────────────────────────────────────────────
    statement: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(
        Float, nullable=False,
        doc="Confidence level [0.5, 0.99]",
    )

    # ── Classification ────────────────────────────────────────
    domain_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text), nullable=False, server_default="{}",
    )

    # ── Resolution ────────────────────────────────────────────
    resolve_by: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_criteria: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    outcome: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending",
        doc="Resolution: pending, correct, incorrect, ambiguous, expired",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_source: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    resolution_evidence: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}"
    )
    actual_vs_predicted: Mapped[float | None] = mapped_column(
        Float, nullable=True
    )

    # ── References ────────────────────────────────────────────
    capture_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_predictions_tenant_outcome", "tenant_id", "outcome"),
        Index("ix_predictions_tenant_resolve_by", "tenant_id", "resolve_by"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return (
            f"<Prediction(id={self.id!s:.8}, "
            f"confidence={self.confidence}, outcome={self.outcome})>"
        )


class CalibrationSnapshot(Base):
    """A point-in-time calibration snapshot — Brier scores, bias analysis.

    Snapshots are computed periodically per domain and track how well
    the user's predictions match reality.
    """

    __tablename__ = "calibration_snapshots"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenant ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Scope ─────────────────────────────────────────────────
    domain: Mapped[str | None] = mapped_column(String(64), nullable=True)
    window_days: Mapped[int] = mapped_column(Integer, nullable=False, default=90)

    # ── Statistics ────────────────────────────────────────────
    resolved_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    ambiguous_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    brier_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    buckets: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    estimate_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    bias_findings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")

    # ── Timestamps ────────────────────────────────────────────
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_cal_tenant_domain_computed", "tenant_id", "domain", "computed_at"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return (
            f"<CalibrationSnapshot(id={self.id!s:.8}, "
            f"domain={self.domain}, brier={self.brier_score})>"
        )


class Challenge(Base):
    """An adversarial challenge — devil's advocate analysis of a proposal.

    Challenges generate structured reports with cited evidence
    and a verdict (proceed, proceed_with_changes, reconsider).
    """

    __tablename__ = "challenges"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenant ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Content ───────────────────────────────────────────────
    proposal: Mapped[str] = mapped_column(Text, nullable=False)
    report: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    verdict: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        doc="Verdict: proceed, proceed_with_changes, reconsider",
    )
    action_taken: Mapped[str | None] = mapped_column(
        String(16), nullable=True,
        doc="What the user did: followed, ignored, modified",
    )

    # ── References ────────────────────────────────────────────
    outcome_prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_graph.predictions.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_cost_usd: Mapped[float] = mapped_column(
        Float, nullable=False, default=0
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_challenges_tenant_created", "tenant_id", "created_at"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return f"<Challenge(id={self.id!s:.8}, verdict={self.verdict})>"


# ── Agent Driver Models ────────────────────────────────────────────


class DriverStat(Base):
    """Aggregated statistics for a driver, bucketed by day.

    Tracks dispatch counts, verification pass rates, costs, and
    durations per driver and task type combination.
    """

    __tablename__ = "driver_stats"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenant ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Dimensions ────────────────────────────────────────────
    driver: Mapped[str] = mapped_column(String(32), nullable=False)
    task_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    window_start: Mapped[datetime] = mapped_column(Date, nullable=False)

    # ── Counters ──────────────────────────────────────────────
    dispatched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    verified_landed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    total_duration_ms: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "driver", "task_type", "window_start",
            name="uq_driver_stats_tenant_driver_task_window",
        ),
        Index("ix_driver_stats_tenant_driver", "tenant_id", "driver"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return (
            f"<DriverStat(id={self.id!s:.8}, "
            f"driver={self.driver}, window={self.window_start})>"
        )


class VerificationRun(Base):
    """A single verification run for a completed task.

    Tracks whether verification passed on attempt 1 or 2 (one-bounce)
    and stores individual verifier results.
    """

    __tablename__ = "verification_runs"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # ── Tenant ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Task Link ─────────────────────────────────────────────
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Verification ──────────────────────────────────────────
    attempt: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1,
        doc="Attempt number: 1 for first try, 2 for one-bounce retry",
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    results: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default="[]",
        doc="Per-verifier results: [{verifier, passed, evidence}]",
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_verification_runs_tenant_task", "tenant_id", "task_id"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return (
            f"<VerificationRun(id={self.id!s:.8}, "
            f"attempt={self.attempt}, passed={self.passed})>"
        )


# Expose autonomy models to prevent ImportErrors in downstream services/routers
from life_graph.autonomy.models import (
    ActionSafetyRule,
    AutoAction,
    TrustScore,
    ApprovalQueueEntry as ApprovalQueue,
    AuditLogEntry as AuditLog,
    AutonomyLevel,
)



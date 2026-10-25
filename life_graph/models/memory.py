"""Memory core, the capture spine and conversations.

SQLAlchemy 2.0 ``mapped_column`` models, split out of ``models/db.py`` on
2026-10-25; ``life_graph.models.db`` still re-exports every one of them.
Every table is tenant-scoped (CHARTER invariant 4)."""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from life_graph.config import settings
from life_graph.models.base import _EMBED_DIM, Base, _utcnow


class Memory(Base):
    """A single memory unit — facts, preferences, decisions, lessons, or observations.

    Memories are the core data atom of the Life Graph. They support
    brain-inspired features: importance tiers, decay, temporal validity,
    trust scoring, supersession chains, and vector embeddings.
    """

    __tablename__ = "memories"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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
    trust_tier: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="verified",
        default="verified",
        doc="Provenance trust tier: self|verified|external|hostile_possible. "
        "Defaults to 'verified' (system-produced); untrusted origin is set "
        "explicitly by the ingesting caller. See core/trust.py.",
    )

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
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Access & Decay ────────────────────────────────────────
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_accessed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decay_rate: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0217,
        doc=(
            "Lambda for the archive-proposal curve: "
            "importance * exp(-decay_rate * days_since_activity). Crossing "
            "settings.decay_archive_threshold makes a memory a candidate for a "
            "removal proposal -- it is never archived automatically. At 0.0217 "
            "that horizon is ~180 days for importance 0.5 and ~212 for 1.0. "
            "This does not drive recall ordering; scoring/ranking.py has its "
            "own recency curve."
        ),
    )

    # ── Reinforcement (Confidence Decay) ──────────────────────
    last_reinforced: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        doc="Last time user confirmed this memory is still accurate",
    )
    reinforced_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of times user confirmed this memory",
    )

    # ── Extraction Provenance ─────────────────────────────────
    extraction_tier: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Which extraction tier created this: regex, spacy, llm, manual",
    )
    extraction_confidence: Mapped[float | None] = mapped_column(
        Float,
        nullable=True,
        doc="Confidence score from the extraction pipeline (0.0-1.0)",
    )

    # ── Impact Scoring (Feature 5) ────────────────────────────
    impact_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.5,
        doc="Learned usefulness from session outcome feedback (0.0-1.0)",
    )
    impact_confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.0,
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
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")

    # ── Status & Owner ────────────────────────────────────────
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    owner: Mapped[str] = mapped_column(String, nullable=False, default="default")

    # ── Deduplication ─────────────────────────────────────────
    content_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True, doc="SHA-256 of normalized content for dedup"
    )

    # ── Capture Spine ─────────────────────────────────────────
    capture_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="Links this memory to the capture event that produced it",
    )

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)
    embedding_model: Mapped[str] = mapped_column(
        String, nullable=False, default=settings.embedding_model
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    memories_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    memories_accessed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    outcome: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        doc="Session result: success, failure, or neutral",
    )
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)

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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_type: Mapped[str] = mapped_column(String, nullable=False, default="event")
    trigger_condition: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    context_match: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    priority: Mapped[str] = mapped_column(String, nullable=False, default="normal")
    status: Mapped[str] = mapped_column(String, nullable=False, default="pending")

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)

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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
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
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)

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
        String(20),
        nullable=False,
        default="created",
        doc="Whether memory was 'created' or 'recalled' in this session",
    )
    was_useful: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")

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


class Procedure(Base):
    """A learned behavioral pattern or strategy.

    Procedures capture recurring workflows distilled from multiple
    sessions.  They store a trigger condition, ordered steps, and
    performance statistics.
    """

    __tablename__ = "procedures"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")

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


class CaptureEvent(Base):
    """A raw capture event — every input to the system, regardless of surface.

    Capture events are the entry point of the Capture Spine. They track
    what came in, from where, and whether it has been processed into
    memories, decisions, or procedures.
    """

    __tablename__ = "capture_events"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Source ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    surface: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Where this came from: orchestrator, mcp, cli, voice, tool, watcher, git",
    )
    modality: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="text",
        doc="Input modality: text, voice, image, structured",
    )

    # ── Content ───────────────────────────────────────────────
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        doc="SHA-256 hash of content for dedup",
    )
    trust_tier: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="external",
        default="external",
        doc="Provenance trust tier derived from surface (default-deny: unknown "
        "surface -> external). See core/trust.py.",
    )

    # ── Processing ────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="received",
        doc="Processing status: received, processed, duplicate, failed",
    )
    yield_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of memories/artifacts produced from this event",
    )

    # ── Timestamps ────────────────────────────────────────────
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
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
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Tenant & Source ───────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    capture_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_graph.capture_events.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Correction Detail ─────────────────────────────────────
    kind: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        doc="Correction type: edit, override, reject, approve",
    )
    original: Mapped[str | None] = mapped_column(Text, nullable=True)
    corrected: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    domain_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
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


# ── Conversation Models ────────────────────────────────────────────
class Conversation(Base):
    """A multi-turn chat thread between the user and their memories."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    last_distilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )

    __table_args__ = (Index("ix_conversations_tenant_updated", "tenant_id", "updated_at"),)

    def __repr__(self) -> str:
        return f"<Conversation(id={self.id!s:.8}, title={self.title})>"


class ConversationMessage(Base):
    """One turn (user question or assistant answer) in a conversation."""

    __tablename__ = "conversation_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    cited_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), nullable=False, default=list
    )
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        CheckConstraint("role IN ('user','assistant')", name="ck_conv_msg_role"),
        Index("ix_conv_messages_conversation_created", "conversation_id", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<ConversationMessage(id={self.id!s:.8}, role={self.role})>"


class ExternalSession(Base):
    """One external AI-tool session (e.g. a Claude Code transcript file)."""

    __tablename__ = "external_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    tool: Mapped[str] = mapped_column(String(64), nullable=False)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    source_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_distilled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "tool", "external_id", name="uq_external_session"),
        Index("ix_external_sessions_tenant_tool", "tenant_id", "tool"),
    )

    def __repr__(self) -> str:
        return f"<ExternalSession(tool={self.tool}, external_id={self.external_id})>"

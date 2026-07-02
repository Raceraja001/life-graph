"""SQLAlchemy 2.0 ORM models for the Life Graph memory system.

All models use mapped_column style with UUID primary keys,
JSONB for schema-less properties, and pgvector for embeddings.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text
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

    # ── Status & Owner ────────────────────────────────────────
    status: Mapped[str] = mapped_column(String, nullable=False, default="active")
    owner: Mapped[str] = mapped_column(String, nullable=False, default="default")

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
    embedding: Mapped[list[float] | None] = mapped_column(
        Vector(768), nullable=True
    )

    # ── Relationships ─────────────────────────────────────────
    memory_links: Mapped[list[MemorySession]] = relationship(
        "MemorySession", back_populates="session", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sessions_started_at", "started_at"),
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

    # ── Relationships ─────────────────────────────────────────
    memory: Mapped[Memory] = relationship("Memory", back_populates="sessions")
    session: Mapped[Session] = relationship("Session", back_populates="memory_links")

    def __repr__(self) -> str:
        return f"<MemorySession(memory={self.memory_id!s:.8}, session={self.session_id!s:.8})>"

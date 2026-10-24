"""Judgment engine: preferences and evidence, interview questions, decisions, predictions, calibration.

SQLAlchemy 2.0 ``mapped_column`` models, split out of ``models/db.py`` on
2026-10-25; ``life_graph.models.db`` still re-exports every one of them.
Every table is tenant-scoped (CHARTER invariant 4)."""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from life_graph.config import settings
from life_graph.models.base import _EMBED_DIM, Base, _utcnow


# ── Era 4: Personal AI ──────────────────────────────────────────────────────
class Preference(Base):
    """A user preference — opinions, likes/dislikes, technology choices, etc.

    Preferences are the evolved form of identity memories, with proper
    evidence tracking, confidence history, and semantic search.
    """

    __tablename__ = "preferences"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")

    # ── Content ───────────────────────────────────────────────
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    choice: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Confidence ────────────────────────────────────────────
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    confidence_history: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")

    # ── Source ────────────────────────────────────────────────
    source: Mapped[str] = mapped_column(String(20), nullable=False, default="explicit")
    source_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Categorization ────────────────────────────────────────
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # ── Validation ────────────────────────────────────────────
    last_validated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    validated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_challenged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)
    embedding_model: Mapped[str] = mapped_column(
        String(50), nullable=False, default=settings.embedding_model
    )

    # ── Status & Timestamps ───────────────────────────────────
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utcnow,
        onupdate=_utcnow,
    )

    # ── Relationships ─────────────────────────────────────────
    evidence_items: Mapped[list[Evidence]] = relationship(
        "Evidence",
        back_populates="preference",
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
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")

    # ── FK to Preference ──────────────────────────────────────
    preference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("preferences.id", ondelete="CASCADE"),
        nullable=False,
    )

    # ── Source ────────────────────────────────────────────────
    source_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Content ───────────────────────────────────────────────
    stance: Mapped[str] = mapped_column(String(20), nullable=False, default="supports")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Scoring ───────────────────────────────────────────────
    credibility: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # ── Metadata ──────────────────────────────────────────────
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)
    embedding_model: Mapped[str] = mapped_column(
        String(50), nullable=False, default=settings.embedding_model
    )

    # ── Status & Timestamps ───────────────────────────────────
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    # ── Relationships ─────────────────────────────────────────
    preference: Mapped[Preference] = relationship("Preference", back_populates="evidence_items")

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        Index("ix_evidence_pref_stance", "preference_id", "stance"),
        Index("ix_evidence_tenant_status", "tenant_id", "status"),
        Index("ix_evidence_source_type", "source_type"),
        Index("ix_evidence_stance", "stance"),
    )

    def __repr__(self) -> str:
        return f"<Evidence(id={self.id!s:.8}, stance={self.stance}, source={self.source_type})>"


class InterviewQuestion(Base):
    """A question the system wants to ask the user proactively.

    Questions are generated from unresolved outcomes, knowledge gaps,
    preference drift, or periodic reflection prompts.
    """

    __tablename__ = "interview_questions"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Tenant & Content ──────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Origin ────────────────────────────────────────────────
    origin: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        doc="Why this question was generated: outcome_resolution, knowledge_gap, drift, reflection",
    )
    origin_ref: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")

    # ── Priority & Status ─────────────────────────────────────
    priority: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
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
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Tenant ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Content ───────────────────────────────────────────────
    title: Mapped[str] = mapped_column(Text, nullable=False)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    options: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    chosen_option: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # ── Status & Source ───────────────────────────────────────
    status: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="candidate",
        doc="Lifecycle: candidate, decided, reviewed, superseded, discarded",
    )
    source: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        doc="Origin: conversation, explicit, challenge",
    )

    # ── Classification ────────────────────────────────────────
    domain_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )
    importance: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)

    # ── Embedding ─────────────────────────────────────────────
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)

    # ── References ────────────────────────────────────────────
    capture_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="Links this decision to the capture event that produced it",
    )
    challenge_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        doc="Links to a challenge that prompted this decision",
    )
    superseded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_graph.decisions.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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
        Float,
        nullable=False,
        doc="Confidence level [0.5, 0.99]",
    )

    # ── Classification ────────────────────────────────────────
    domain_tags: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
    )

    # ── Resolution ────────────────────────────────────────────
    resolve_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_criteria: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    outcome: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        default="pending",
        doc="Resolution: pending, correct, incorrect, ambiguous, expired",
    )
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resolution_evidence: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    actual_vs_predicted: Mapped[float | None] = mapped_column(Float, nullable=True)

    # ── References ────────────────────────────────────────────
    capture_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
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
            f"<Prediction(id={self.id!s:.8}, confidence={self.confidence}, outcome={self.outcome})>"
        )


class CalibrationSnapshot(Base):
    """A point-in-time calibration snapshot — Brier scores, bias analysis.

    Snapshots are computed periodically per domain and track how well
    the user's predictions match reality.
    """

    __tablename__ = "calibration_snapshots"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # ── Tenant ────────────────────────────────────────────────
    tenant_id: Mapped[str] = mapped_column(String, nullable=False)

    # ── Content ───────────────────────────────────────────────
    proposal: Mapped[str] = mapped_column(Text, nullable=False)
    report: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    verdict: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        doc="Verdict: proceed, proceed_with_changes, reconsider",
    )
    action_taken: Mapped[str | None] = mapped_column(
        String(16),
        nullable=True,
        doc="What the user did: followed, ignored, modified",
    )

    # ── References ────────────────────────────────────────────
    outcome_prediction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("life_graph.predictions.id", ondelete="SET NULL"),
        nullable=True,
    )
    total_cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0)

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

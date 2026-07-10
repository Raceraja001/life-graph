"""SQLAlchemy 2.0 ORM models for Era 8: Autonomous AI.

Six models covering safety classification, action execution,
trust scoring, approval workflows, audit logging, and autonomy levels.

All models use TEXT primary keys (not UUID) for simpler serialization.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.models.db import Base, _utcnow


class ActionSafetyRule(Base):
    """A rule defining how an action should be classified and guarded.

    Rules are matched against action names via glob patterns and
    determine risk level, trust thresholds, and reversibility.
    """

    __tablename__ = "action_safety_rules"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)

    # ── Rule Definition ───────────────────────────────────────
    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    action_pattern: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False, default="general")
    risk_level: Mapped[str] = mapped_column(Text, nullable=False, default="dangerous")
    trust_threshold: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, default=0.7
    )

    # ── Guardrail Flags ───────────────────────────────────────
    is_guardrail: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    max_blast_radius: Mapped[int | None] = mapped_column(Integer, nullable=True)
    requires_staging: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    rollback_template: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Control ───────────────────────────────────────────────
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("ix_asr_tenant", "tenant_id"),
        Index("ix_asr_risk", "tenant_id", "risk_level"),
        Index("ix_asr_category", "tenant_id", "category"),
        Index("ix_asr_enabled", "tenant_id", "enabled"),
        Index("ix_asr_pattern", "action_pattern"),
        Index("uq_asr_tenant_action", "tenant_id", "action_name", unique=True),
    )

    def __repr__(self) -> str:
        return (
            f"<ActionSafetyRule(id={self.id[:8]}, "
            f"action={self.action_name}, risk={self.risk_level})>"
        )


class AutoAction(Base):
    """A recorded autonomous action — the execution log of an auto-performed task.

    Tracks the full lifecycle from queuing through execution to
    potential rollback.
    """

    __tablename__ = "auto_actions"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Action Definition ─────────────────────────────────────
    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    action_command: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Trigger ───────────────────────────────────────────────
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_detail: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Safety Link ───────────────────────────────────────────
    safety_rule_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("action_safety_rules.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── State ─────────────────────────────────────────────────
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")

    # ── Result ────────────────────────────────────────────────
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stdout: Mapped[str | None] = mapped_column(Text, nullable=True)
    stderr: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Rollback ──────────────────────────────────────────────
    is_reversible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    rollback_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rollback_action_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Approval ──────────────────────────────────────────────
    approval_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("approval_queue.id", ondelete="SET NULL"),
        nullable=True,
    )
    approved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Timestamps ────────────────────────────────────────────
    queued_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
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

    __table_args__ = (
        Index("ix_aa_tenant_agent", "tenant_id", "agent_id"),
        Index("ix_aa_tenant_status", "tenant_id", "status"),
        Index("ix_aa_project", "tenant_id", "project_id"),
        Index("ix_aa_safety_rule", "safety_rule_id"),
        Index("ix_aa_approval", "approval_id"),
        Index("ix_aa_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AutoAction(id={self.id[:8]}, "
            f"action={self.action_name}, status={self.status})>"
        )


class TrustScore(Base):
    """Bayesian trust score for an agent–action pair.

    Tracks success/failure history, streak bonuses, decay rates,
    and optional manual overrides.
    """

    __tablename__ = "trust_scores"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    project_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Score ─────────────────────────────────────────────────
    score: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.0
    )
    total_successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    peak_score: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.0
    )

    # ── Timestamps ────────────────────────────────────────────
    last_action_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Tuning ────────────────────────────────────────────────
    decay_rate: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.05
    )
    failure_penalty: Mapped[float] = mapped_column(
        Numeric(4, 3), nullable=False, default=0.5
    )

    # ── Manual Override ───────────────────────────────────────
    manual_override: Mapped[float | None] = mapped_column(
        Numeric(4, 3), nullable=True
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    override_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index(
            "uq_ts_tenant_agent_action_project",
            "tenant_id", "agent_id", "action_type", "project_id",
            unique=True,
        ),
        Index("ix_ts_agent", "tenant_id", "agent_id"),
        Index("ix_ts_action", "tenant_id", "action_type"),
        Index("ix_ts_project", "tenant_id", "project_id"),
        Index("ix_ts_score", "tenant_id", "score"),
    )

    def __repr__(self) -> str:
        return (
            f"<TrustScore(id={self.id[:8]}, agent={self.agent_id}, "
            f"action={self.action_type}, score={self.score})>"
        )


class ApprovalQueueEntry(Base):
    """An action awaiting human approval before execution.

    Supports priority ordering, batch approvals, timeout expiration,
    and escalation tracking.
    """

    __tablename__ = "approval_queue"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Action ────────────────────────────────────────────────
    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    action_command: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(Text, nullable=False, default="general")
    project_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Trigger ───────────────────────────────────────────────
    trigger_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_detail: Mapped[str] = mapped_column(Text, nullable=False)
    estimated_impact: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Safety Link ───────────────────────────────────────────
    safety_rule_id: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("action_safety_rules.id", ondelete="SET NULL"),
        nullable=True,
    )

    # ── Status ────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=100)

    # ── Resolution ────────────────────────────────────────────
    resolved_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Batch & Timeout ───────────────────────────────────────
    also_trust: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    batch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    timeout_hours: Mapped[int] = mapped_column(Integer, nullable=False, default=24)
    escalation_sent: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="[]"
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_aq_tenant_status", "tenant_id", "status"),
        Index("ix_aq_tenant_agent", "tenant_id", "agent_id"),
        Index("ix_aq_project", "tenant_id", "project_id"),
        Index("ix_aq_risk", "tenant_id", "risk_level"),
        Index("ix_aq_batch", "batch_id"),
        Index("ix_aq_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalQueueEntry(id={self.id[:8]}, "
            f"action={self.action_name}, status={self.status})>"
        )


class AuditLogEntry(Base):
    """Immutable audit record for every autonomous action.

    No updated_at — audit log entries are write-once.
    """

    __tablename__ = "audit_log"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Actor ─────────────────────────────────────────────────
    actor_type: Mapped[str] = mapped_column(Text, nullable=False, default="agent")
    actor_id: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Action ────────────────────────────────────────────────
    action_type: Mapped[str] = mapped_column(Text, nullable=False)
    action_name: Mapped[str] = mapped_column(Text, nullable=False)
    action_command: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    classification_reasoning: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── References ────────────────────────────────────────────
    project_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    auto_action_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    related_audit_id: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── State ─────────────────────────────────────────────────
    before_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    after_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Result ────────────────────────────────────────────────
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Timestamp (immutable — no updated_at) ─────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_al_tenant", "tenant_id", "created_at"),
        Index("ix_al_agent", "tenant_id", "agent_id"),
        Index("ix_al_action", "tenant_id", "action_type"),
        Index("ix_al_project", "tenant_id", "project_id"),
        Index("ix_al_auto_action", "auto_action_id"),
        Index("ix_al_approval", "approval_id"),
        Index("ix_al_result", "tenant_id", "result"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLogEntry(id={self.id[:8]}, "
            f"action={self.action_name}, result={self.result})>"
        )


class AutonomyLevel(Base):
    """Progressive autonomy level for a tenant–project pair.

    Tracks promotion/demotion history and success counters
    across risk categories.
    """

    __tablename__ = "autonomy_levels"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[str] = mapped_column(
        Text, primary_key=True, default=lambda: str(uuid.uuid4())
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Level ─────────────────────────────────────────────────
    level: Mapped[str] = mapped_column(Text, nullable=False, default="L0")
    level_description: Mapped[str] = mapped_column(
        Text, nullable=False, default="Ask Everything"
    )

    # ── Success Counters ──────────────────────────────────────
    safe_successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    moderate_successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dangerous_successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Promotion ─────────────────────────────────────────────
    promotion_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    promotion_threshold: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        server_default='{"L0_to_L1": 20, "L1_to_L2": 50, "L2_to_L3": 100}',
    )

    # ── Demotion ──────────────────────────────────────────────
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    demotion_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # ── Manual Override ───────────────────────────────────────
    manual_level: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_set_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    manual_set_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Configuration ─────────────────────────────────────────
    moderate_timeout_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=15
    )
    l3_opted_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    l3_min_trust: Mapped[float] = mapped_column(
        Numeric(3, 2), nullable=False, default=0.90
    )

    # ── Aggregate Stats ───────────────────────────────────────
    total_auto_actions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_successes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    success_rate: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    last_promotion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_demotion_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_audit_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index("uq_al_tenant_project", "tenant_id", "project_id", unique=True),
        Index("ix_alvl_tenant_level", "tenant_id", "level"),
        Index("ix_alvl_tenant_project", "tenant_id", "project_id"),
        Index("ix_alvl_promo", "tenant_id", "promotion_eligible"),
    )

    def __repr__(self) -> str:
        return (
            f"<AutonomyLevel(id={self.id[:8]}, "
            f"project={self.project_id}, level={self.level})>"
        )

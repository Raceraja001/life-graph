"""SQLAlchemy 2.0 ORM models for Era 5: Self-Improving Agent.

All models use mapped_column style with UUID primary keys,
JSONB for schema-less data, and Numeric for percentages/costs.
Multi-tenant: every model has a `tenant_id` column.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, CheckConstraint, DateTime, Float, ForeignKey,
    Index, Integer, Numeric, String, Text, text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from life_graph.models.db import Base, _utcnow


class EvalSuite(Base):
    """An evaluation suite — a named set of test cases for a task type."""

    __tablename__ = "eval_suites"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Thresholds & Toggles ──────────────────────────────────
    accuracy_threshold_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default="90.00",
    )
    auto_optimize_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    max_consecutive_fails: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3,
    )

    # ── Stats ─────────────────────────────────────────────────
    case_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    last_accuracy_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )

    # ── Timestamps ────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow,
    )

    # ── Relationships ─────────────────────────────────────────
    cases: Mapped[list[EvalCase]] = relationship(
        "EvalCase", back_populates="suite", cascade="all, delete-orphan",
    )
    runs: Mapped[list[EvalRun]] = relationship(
        "EvalRun", back_populates="suite", cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("uq_eval_suites_tenant_task", "tenant_id", "task_type", unique=True),
        Index("ix_eval_suites_tenant", "tenant_id"),
        Index(
            "ix_eval_suites_auto_opt", "auto_optimize_enabled",
            postgresql_where=text("auto_optimize_enabled = true"),
        ),
    )

    def __repr__(self) -> str:
        return f"<EvalSuite(id={self.id!s:.8}, task={self.task_type}, name={self.name})>"


class EvalCase(Base):
    """A single test case within an eval suite."""

    __tablename__ = "eval_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_suites.id", ondelete="CASCADE"),
        nullable=False,
    )
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    expected_output: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_type: Mapped[str] = mapped_column(
        Text, nullable=False, default="exact_match",
    )
    scoring_config: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="{}",
    )
    metadata_: Mapped[dict] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}",
    )
    source: Mapped[str] = mapped_column(
        Text, nullable=False, default="manual",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )

    # ── Relationships ─────────────────────────────────────────
    suite: Mapped[EvalSuite] = relationship(
        "EvalSuite", back_populates="cases",
    )
    results: Mapped[list[EvalResult]] = relationship(
        "EvalResult", back_populates="case", cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "scoring_type IN ('exact_match','contains','regex',"
            "'semantic_similarity','llm_judge')",
            name="ck_eval_cases_scoring_type",
        ),
        Index(
            "ix_eval_cases_suite_active", "suite_id",
            postgresql_where=text("is_active = true"),
        ),
        Index("ix_eval_cases_suite_scoring", "suite_id", "scoring_type"),
    )

    def __repr__(self) -> str:
        return f"<EvalCase(id={self.id!s:.8}, input={self.input_text[:40]!r})>"


class EvalRun(Base):
    """A single execution run of an eval suite."""

    __tablename__ = "eval_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_suites.id", ondelete="CASCADE"),
        nullable=False,
    )
    prompt_version_id: Mapped[str] = mapped_column(Text, nullable=False)
    trigger: Mapped[str] = mapped_column(
        Text, nullable=False, default="manual",
    )
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="running",
    )

    # ── Counts ────────────────────────────────────────────────
    total_cases: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    failed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    errored: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── Metrics ───────────────────────────────────────────────
    accuracy_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )
    avg_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True,
    )
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Relationships ─────────────────────────────────────────
    suite: Mapped[EvalSuite] = relationship(
        "EvalSuite", back_populates="runs",
    )
    results: Mapped[list[EvalResult]] = relationship(
        "EvalResult", back_populates="run", cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "trigger IN ('manual','nightly_cron','optimization_test',"
            "'regression_check')",
            name="ck_eval_runs_trigger",
        ),
        CheckConstraint(
            "status IN ('running','completed','error','cancelled')",
            name="ck_eval_runs_status",
        ),
        Index("ix_eval_runs_suite_started", "suite_id", "started_at"),
        Index("ix_eval_runs_prompt_ver", "prompt_version_id"),
        Index("ix_eval_runs_trigger_started", "trigger", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<EvalRun(id={self.id!s:.8}, status={self.status})>"


class EvalResult(Base):
    """Result for a single test case within an eval run."""

    __tablename__ = "eval_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_cases.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(Text, nullable=False)
    actual_output: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True,
    )
    failure_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    similarity_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True,
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )

    # ── Relationships ─────────────────────────────────────────
    run: Mapped[EvalRun] = relationship(
        "EvalRun", back_populates="results",
    )
    case: Mapped[EvalCase] = relationship(
        "EvalCase", back_populates="results",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pass','fail','error')",
            name="ck_eval_results_status",
        ),
        Index("ix_eval_results_run", "run_id"),
        Index("ix_eval_results_case", "case_id"),
        Index("ix_eval_results_run_status", "run_id", "status"),
        Index(
            "ix_eval_results_run_failure", "run_id", "failure_type",
            postgresql_where=text("status = 'fail'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<EvalResult(id={self.id!s:.8}, status={self.status})>"


class PromptVersion(Base):
    """A versioned prompt template for a specific task type."""

    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    few_shot_examples: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default="[]",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
    )
    eval_score: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )
    created_by: Mapped[str] = mapped_column(
        Text, nullable=False, default="human",
    )
    optimization_run_id: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )

    __table_args__ = (
        Index(
            "uq_prompt_ver_active", "tenant_id", "task_type",
            unique=True,
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "uq_prompt_ver_number", "tenant_id", "task_type", "version_number",
            unique=True,
        ),
        Index("ix_prompt_ver_lookup", "tenant_id", "task_type", "version_number"),
    )

    def __repr__(self) -> str:
        return (
            f"<PromptVersion(id={self.id!s:.8}, "
            f"task={self.task_type}, v{self.version_number}, "
            f"active={self.is_active})>"
        )


class OptimizationRun(Base):
    """Record of a prompt optimization attempt."""

    __tablename__ = "optimization_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    suite_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("eval_suites.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_type: Mapped[str] = mapped_column(Text, nullable=False)
    trigger_eval_run_id: Mapped[str] = mapped_column(Text, nullable=False)

    # ── Accuracy tracking ─────────────────────────────────────
    trigger_accuracy_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )
    threshold_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )

    # ── Training data ─────────────────────────────────────────
    training_positive_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    training_negative_count: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )

    # ── Candidate version ─────────────────────────────────────
    candidate_version_id: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    candidate_eval_run_id: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    candidate_accuracy_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )

    # ── Previous version ──────────────────────────────────────
    previous_version_id: Mapped[str | None] = mapped_column(
        Text, nullable=True,
    )
    previous_accuracy_pct: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 2), nullable=True,
    )

    # ── Status ────────────────────────────────────────────────
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="running",
    )
    regression_details: Mapped[dict | None] = mapped_column(
        JSONB, nullable=True,
    )

    # ── Review ────────────────────────────────────────────────
    review_decision: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    # ── Cost tracking ─────────────────────────────────────────
    optimization_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    eval_tokens: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    optimization_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True,
    )
    eval_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True,
    )
    total_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('running','testing','deployed','no_improvement',"
            "'needs_review','rejected','error')",
            name="ck_optimization_runs_status",
        ),
        Index("ix_opt_runs_tenant_started", "tenant_id", "started_at"),
        Index("ix_opt_runs_task_started", "task_type", "started_at"),
        Index("ix_opt_runs_status", "status"),
        Index(
            "ix_opt_runs_needs_review", "status",
            postgresql_where=text("status = 'needs_review'"),
        ),
    )

    def __repr__(self) -> str:
        return f"<OptimizationRun(id={self.id!s:.8}, status={self.status})>"


class NightlyRunLog(Base):
    """Log entry for a nightly evaluation + optimization run."""

    __tablename__ = "nightly_run_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, default="running",
    )

    # ── Counters ──────────────────────────────────────────────
    task_types_evaluated: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    optimizations_triggered: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    optimizations_deployed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )
    optimizations_flagged: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0,
    )

    # ── Cost tracking ─────────────────────────────────────────
    total_eval_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True,
    )
    total_opt_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True,
    )
    total_cost_usd: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 6), nullable=True,
    )
    duration_seconds: Mapped[float | None] = mapped_column(
        Float, nullable=True,
    )
    summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Timestamps ────────────────────────────────────────────
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('running','completed','partial','error')",
            name="ck_nightly_run_log_status",
        ),
        Index("ix_nightly_log_tenant_started", "tenant_id", "started_at"),
    )

    def __repr__(self) -> str:
        return f"<NightlyRunLog(id={self.id!s:.8}, status={self.status})>"

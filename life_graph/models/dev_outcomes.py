"""The dev-task outcome log: one row per dispatch of a dev task.

docs/specs/agent-drivers.md, "Escalation ladder, starting floor, outcome log
(2026-11-28)". ``record_outcome`` (services/dev/outcomes.py) keeps *trust* per
driver and change kind; this row keeps what calibration needs and trust lacks:
which driver/model ran at which ladder rung and why, the escalations, rounds,
verification and review verdicts, the final outcome, the owner's decision once
known, duration, cost -- and the tier a future rules router *would* have picked
(``shadow_tier``, never consulted).

Migration 068 creates it. Tenant-scoped (CHARTER invariant 4). ``task_id`` is a
plain string with no foreign key: the dispatch test endpoint's throwaway ids
have no ``agent_tasks`` row and are logged too.
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.models.base import Base, _utcnow


class DevOutcomeLog(Base):
    """What one dispatch of a dev task ran on, why, and how it ended."""

    __tablename__ = "dev_outcome_log"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[str] = mapped_column(String(64), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # 1 = the task's first dispatch; a re-run or continuation counts up.
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    persona: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # SHA-256 of the normalized instruction (the floor's "failed before" key).
    instruction_sha: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    # Where it started and why: selection | pinned | floor: <why> | ...
    start_driver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    start_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    start_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    start_reason: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    # Where it ended (the last rung climbed, or the start).
    final_driver: Mapped[str | None] = mapped_column(String(64), nullable=True)
    final_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    final_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # [{from, to, reason, attempt}] and the climbs that were refused.
    escalations: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # The ladder or the floor (not today's selection or a pin) put it on the top rung.
    reached_top: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    # Verification attempts after the first (bounce + fix rounds).
    rounds_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # passed | failed | unverifiable | not_run
    verification: Mapped[str] = mapped_column(String(16), nullable=False, default="not_run")
    # [{reviewer, verdict, concern?}]; verdict approved | objected |
    # not_reviewed (due, no verdict: fail-closed) | skipped (off / nothing to review).
    reviews: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # Overall: objected > not_reviewed > approved > skipped (no review ran).
    review_verdict: Mapped[str] = mapped_column(String(16), nullable=False, default="not_reviewed")
    # landed | succeeded | no_changes | needs_human | parked | budget_denied | failed | error
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    # merged | pr_rejected | closed, from record_outcome; null while unknown.
    owner_decision: Mapped[str | None] = mapped_column(String(24), nullable=True)
    owner_decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # SHADOW: the tier the future rules router would have picked; never used.
    shadow_tier: Mapped[str | None] = mapped_column(String(16), nullable=True)
    shadow_reasons: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (
        Index("ix_dev_outcome_log_tenant_created", "tenant_id", "created_at"),
        Index("ix_dev_outcome_log_task", "tenant_id", "task_id"),
        Index("ix_dev_outcome_log_instruction", "tenant_id", "project_id", "instruction_sha"),
    )

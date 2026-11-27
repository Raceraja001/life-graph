"""Dev-task groups (parallel plans, arena races) and PR watches (Phase 4b).

docs/specs/agent-drivers.md, "Phase 4b (2026-11-27)". A *group* ties several
dev tasks together: a **team** (a plan whose tasks run in parallel on their own
branches, then one integration task) or an **arena** race (one instruction on
several drivers/accounts, the owner picks the winner). The tasks themselves stay
ordinary ``agent_tasks`` rows; the group row holds the group's own state so a
restart resumes it. A *PR watch* is the feedback loop's state for one task's
open pull request: what it has already handed back (``seen``) and how many
rounds it used.

Migration 066 creates both tables. Tenant-scoped (CHARTER invariant 4).
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.models.base import Base, _utcnow


class DevTaskGroup(Base):
    """A team (parallel plan) or an arena race: several dev tasks, one state."""

    __tablename__ = "dev_task_groups"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # team | arena (validated in services, not an enum: schema-less).
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # team: running | integrating | awaiting_approval | failed | cancelled
    # arena: racing | ready_to_pick | decided | cancelled
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    # team: the plan task's id; arena: null.
    source_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # team: max_parallel, worker_ids, integration_task_id, reason;
    # arena: instruction, racers [{task_id, driver, account_id}], winner_task_id.
    properties: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (Index("ix_dev_task_groups_state", "tenant_id", "kind", "status"),)


class PrWatch(Base):
    """The PR feedback loop's state for one dev task's open pull request."""

    __tablename__ = "pr_watches"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    pr_url: Mapped[str] = mapped_column(String(300), nullable=False)
    # watching | feeding_back | needs_you | merged | closed | stopped
    state: Mapped[str] = mapped_column(String(20), nullable=False, default="watching")
    rounds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Dedupe keys already handed back: check:<sha>:<name>, review:/comment:/inline:<id>,
    # conflict:<sha>. Survives restarts.
    seen: Mapped[list] = mapped_column(
        JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb")
    )
    # Comments older than this are not feedback (they predate the watch).
    since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_feedback: Mapped[str | None] = mapped_column(String(300), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        UniqueConstraint("tenant_id", "task_id", name="uq_pr_watches_task"),
        Index("ix_pr_watches_state", "state"),
    )

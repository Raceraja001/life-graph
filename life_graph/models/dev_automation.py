"""Dev automation: intake sources, the backlog, dev-task schedules, breakers.

docs/specs/dev-automation.md (Phase 4a of the race-app migration). Work
*arrives* from intake sources (GitHub issues, failing CI, life-graph
intentions, TODO comments) as backlog items, *runs on a schedule* as dev-task
jobs, and a per-source / per-job **circuit breaker** stops automatic starts
after repeated identical failures. Nothing here approves, publishes or merges:
every task goes through the normal dev-task pipeline and its approvals.

Migration 065 creates every table. Tenant-scoped (CHARTER invariant 4).
"""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from life_graph.models.base import Base, _utcnow

SOURCE_KINDS = ("github_issues", "failing_ci", "life_graph_intentions", "todo_comments")
MODES = ("plan", "ask", "auto")
BACKLOG_STATUSES = ("new", "queued", "running", "done", "skipped", "failed")


class DevAutomationSettings(Base):
    """One row per tenant: the limits, digest and breaker settings, plus run state.

    ``settings`` holds ``intake`` (``maxConcurrent``, ``maxPerDay``),
    ``digest`` (``enabled``, ``time``), ``breaker`` (``enabled``,
    ``threshold``) and ``timezone``, validated by
    services/dev/automation/settings.py. ``state`` is written by the
    automation itself (the last digest's day and window end). No row = the
    defaults: everything off except the breaker, which only ever stops things.
    """

    __tablename__ = "dev_automation_settings"

    tenant_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    state: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    updated_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )


class DevIntakeSource(Base):
    """Where backlog items come from, and how their tasks run."""

    __tablename__ = "dev_intake_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str | None] = mapped_column(String(80), nullable=True)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    # github_issues: label; todo_comments: marker; life_graph_intentions: tag.
    filter: Mapped[str | None] = mapped_column(String(100), nullable=True)
    persona: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="ask")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    poll_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    comment_on_issue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_polled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "kind IN ('github_issues','failing_ci','life_graph_intentions','todo_comments')",
            name="ck_dev_intake_sources_kind",
        ),
        CheckConstraint("mode IN ('plan','ask','auto')", name="ck_dev_intake_sources_mode"),
        CheckConstraint(
            "poll_minutes BETWEEN 5 AND 1440", name="ck_dev_intake_sources_poll_minutes"
        ),
        Index("ix_dev_intake_sources_tenant", "tenant_id"),
    )


class DevBacklogItem(Base):
    """One piece of work found by a source. ``external_key`` is never re-added."""

    __tablename__ = "dev_backlog"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("dev_intake_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    external_key: Mapped[str] = mapped_column(String(300), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="new")
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # comments: stages already commented on the issue; started_by: auto | owner.
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "external_key", name="uq_dev_backlog_tenant_key"),
        CheckConstraint(
            "status IN ('new','queued','running','done','skipped','failed')",
            name="ck_dev_backlog_status",
        ),
        Index("ix_dev_backlog_tenant_status", "tenant_id", "status"),
    )


class DevSchedule(Base):
    """A dev-task job: an instruction run on days at a local time, or after another job."""

    __tablename__ = "dev_schedules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    persona: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mode: Mapped[str] = mapped_column(String(8), nullable=False, default="ask")
    # 0-6 = Sunday-Saturday, in the tenant's timezone.
    days: Mapped[list[int]] = mapped_column(ARRAY(Integer), nullable=False)
    time: Mapped[str] = mapped_column(String(5), nullable=False)
    after_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dev_schedules.id", ondelete="SET NULL"), nullable=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint("mode IN ('plan','ask','auto')", name="ck_dev_schedules_mode"),
        Index("ix_dev_schedules_tenant", "tenant_id"),
    )


class DevScheduleRun(Base):
    """One handled slot of a job: claimed before it starts, so it runs once."""

    __tablename__ = "dev_schedule_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("dev_schedules.id", ondelete="CASCADE"), nullable=False
    )
    # The tenant-local day the slot belongs to ("YYYY-MM-DD").
    slot_date: Mapped[str] = mapped_column(String(10), nullable=False)
    # scheduled | chain | manual
    trigger: Mapped[str] = mapped_column(String(16), nullable=False)
    predecessor_task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # starting | started | missed | failed | skipped_kill_switch | skipped_breaker |
    # skipped_budget | skipped_overlap
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    task_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        Index(
            "uq_dev_schedule_runs_slot",
            "schedule_id",
            "slot_date",
            unique=True,
            postgresql_where=text("trigger = 'scheduled'"),
        ),
        Index(
            "uq_dev_schedule_runs_chain",
            "schedule_id",
            "predecessor_task_id",
            unique=True,
            postgresql_where=text("trigger = 'chain'"),
        ),
        Index("ix_dev_schedule_runs_job", "tenant_id", "schedule_id", "created_at"),
    )


class DevAutomationBreaker(Base):
    """The circuit breaker of one source (``intake:<id>``) or job (``schedule:<id>``)."""

    __tablename__ = "dev_automation_breakers"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    key: Mapped[str] = mapped_column(String(120), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    tripped: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    tripped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Task ids already counted (newest last, capped): each outcome counts once.
    counted: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (UniqueConstraint("tenant_id", "key", name="uq_dev_automation_breakers_key"),)

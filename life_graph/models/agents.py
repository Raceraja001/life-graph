"""Kernel and driver models: sessions, personas, tasks, projects, workflows, approvals, driver runs.

SQLAlchemy 2.0 ``mapped_column`` models, split out of ``models/db.py`` on
2026-10-25; ``life_graph.models.db`` still re-exports every one of them.
Every table is tenant-scoped (CHARTER invariant 4)."""

from __future__ import annotations

import uuid
from datetime import datetime  # noqa: TC003

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from life_graph.models.base import _EMBED_DIM, Base, _utcnow


# ── OS Kernel Models ──────────────────────────────────────────
class AgentSession(Base):
    """Tracks routing decisions and conversation chains across agent handoffs."""

    __tablename__ = "agent_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    user_message: Mapped[str] = mapped_column(Text, nullable=False)
    classified_intent: Mapped[str | None] = mapped_column(String(30), nullable=True)
    classification_conf: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    routed_to: Mapped[str | None] = mapped_column(String(100), nullable=True)
    handoff_chain: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    total_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )  # active|completed|failed|abandoned
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    memory_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("sessions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str] = mapped_column(
        String(100), nullable=False, default="gemini/gemini-2.5-flash"
    )
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)
    max_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=4096)
    allowed_tools: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    intent_tags: Mapped[list[str] | None] = mapped_column(ARRAY(String), nullable=True)
    icon: Mapped[str | None] = mapped_column(String(10), nullable=True)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    use_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        String(32),
        nullable=True,
        doc="Default driver for this persona (local, claude_code, codex, etc.)",
    )
    verifier_chain: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
        doc="Ordered list of verifier names to run after task completion",
    )
    context_profile: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
        doc="Context packet configuration: which sections to include, token budgets",
    )
    task_types: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default="{}",
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
        return f"<AgentPersona(id={self.id!s:.8}, name={self.name}, builtin={self.is_builtin})>"


class AgentTask(Base):
    """An agent task — like an OS process.

    Tracks the full lifecycle of a spawned agent execution.
    """

    __tablename__ = "agent_tasks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    task_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued"
    )  # queued|running|completed|failed|cancelled|timeout
    priority: Mapped[str] = mapped_column(
        String(10), nullable=False, default="normal"
    )  # low|normal|high|critical
    input: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    result: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="[]")
    token_usage: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    model_used: Mapped[str | None] = mapped_column(String(100), nullable=True)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, default=2)
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
    project_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    # ── Era 7 additions ──
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_type: Mapped[str] = mapped_column(String(30), nullable=False, default="general")
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_by_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    root_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    depth: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    on_child_failure: Mapped[str] = mapped_column(String(20), nullable=False, default="continue")
    status_history: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    workflow_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    workflow_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    tags: Mapped[list[str]] = mapped_column(
        ARRAY(String(50)),
        nullable=False,
        server_default="{}",
        default=list,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
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
        Index("ix_agent_tasks_tenant_status", "tenant_id", "status"),
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
        return f"<AgentTask(id={self.id!s:.8}, agent={self.agent_name}, status={self.status})>"


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
        String(64),
        nullable=False,
        default="legacy",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    agent_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    input: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    run_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_run_status: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    last_run_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey(
            "agent_tasks.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )
    next_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    max_retries: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )
    timeout_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=600,
    )
    properties: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
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
        return f"<ScheduledJob(id={self.id!s:.8}, name={self.name}, cron={self.cron_expression})>"


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
        String(64),
        nullable=False,
        default="legacy",
    )
    name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )
    path: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    git_url: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    git_branch: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
    )
    language: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
    )
    framework: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    dependency_file: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    dependency_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    file_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    recent_commits: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    scan_metadata: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    last_scanned_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
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
            "tenant_id",
            "name",
            unique=True,
        ),
        Index(
            "ix_projects_tenant",
            "tenant_id",
            "is_active",
        ),
        Index(
            "ix_projects_language",
            "tenant_id",
            "language",
        ),
    )

    def __repr__(self) -> str:
        return f"<Project(id={self.id!s:.8}, name={self.name}, lang={self.language})>"


class AdvisorSession(Base):
    """A Q&A session with the personal advisor.

    Tracks questions asked, answers given, and what evidence/preferences
    were used to form the answer.
    """

    __tablename__ = "advisor_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    reasoning: Mapped[str | None] = mapped_column(Text, nullable=True)
    sources_used: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    preferences_cited: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.5)
    consensus_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")
    query: Mapped[str] = mapped_column(Text, nullable=False)
    sources_searched: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    evidence_found: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    evidence_added: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    preferences_affected: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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
        UUID(as_uuid=True),
        ForeignKey("agent_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    attachments: Mapped[list] = mapped_column(JSONB, nullable=False, server_default="[]")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="unread")
    priority: Mapped[str] = mapped_column(String(10), nullable=False, default="medium")
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)

    # Relationships
    steps: Mapped[list[WorkflowStep]] = relationship(
        "WorkflowStep", back_populates="workflow", cascade="all, delete-orphan"
    )
    runs: Mapped[list[WorkflowRun]] = relationship(
        "WorkflowRun", back_populates="workflow", cascade="all, delete-orphan"
    )

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
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
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

    workflow: Mapped[Workflow] = relationship("Workflow", back_populates="steps")

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
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="manual")
    triggered_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    input_params: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    output_summary: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    workflow: Mapped[Workflow] = relationship("Workflow", back_populates="runs")
    step_runs: Mapped[list[WorkflowStepRun]] = relationship(
        "WorkflowStepRun", back_populates="run", cascade="all, delete-orphan"
    )

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
        UUID(as_uuid=True),
        ForeignKey("workflow_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workflow_steps.id", ondelete="CASCADE"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    output: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    properties: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    run: Mapped[WorkflowRun] = relationship("WorkflowRun", back_populates="step_runs")

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
        UUID(as_uuid=True),
        ForeignKey("agent_tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_type: Mapped[str] = mapped_column(String(30), nullable=False, default="finding")
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(String(50)), nullable=True)
    relevance_score: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    access_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(_EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
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


class Approval(Base):
    """A unified human-in-the-loop item awaiting an approve/reject decision.

    Polymorphic across subsystems via ``kind``/``source``: promotions
    (self-improving) today; merges, contradictions, and weekly-review drafts
    as producers are added. Distinct from the autonomy ``approval_queue``
    (shell-command HITL). Multi-tenant — every query filters by ``tenant_id``.
    """

    __tablename__ = "approvals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False, default="legacy")

    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    resolved_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','rejected')",
            name="ck_approvals_status",
        ),
        Index("ix_approvals_tenant_status", "tenant_id", "status"),
        Index(
            "uq_approvals_source_ref",
            "tenant_id",
            "source",
            "source_ref",
            unique=True,
            postgresql_where=text("source_ref IS NOT NULL"),
        ),
    )

    def __repr__(self) -> str:
        return f"<Approval(id={self.id!s:.8}, kind={self.kind}, status={self.status})>"


# ── Agent Driver Models ────────────────────────────────────────────
class DriverStat(Base):
    """Aggregated statistics for a driver, bucketed by day.

    Tracks dispatch counts, verification pass rates, costs, and
    durations per driver and task type combination.
    """

    __tablename__ = "driver_stats"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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
    total_duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # ── Indexes ───────────────────────────────────────────────
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "driver",
            "task_type",
            "window_start",
            name="uq_driver_stats_tenant_driver_task_window",
        ),
        Index("ix_driver_stats_tenant_driver", "tenant_id", "driver"),
        {"schema": "life_graph"},
    )

    def __repr__(self) -> str:
        return f"<DriverStat(id={self.id!s:.8}, driver={self.driver}, window={self.window_start})>"


class VerificationRun(Base):
    """A single verification run for a completed task.

    Tracks whether verification passed on attempt 1 or 2 (one-bounce)
    and stores individual verifier results.
    """

    __tablename__ = "verification_runs"

    # ── Identity ──────────────────────────────────────────────
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

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
        Integer,
        nullable=False,
        default=1,
        doc="Attempt number: 1 for first try, 2 for one-bounce retry",
    )
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    results: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
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
        return f"<VerificationRun(id={self.id!s:.8}, attempt={self.attempt}, passed={self.passed})>"


class AgentRunStep(Base):
    """One step of a driver run: what the agent said, called, got back.

    Written by services/trajectories.py from the ``driver:steps`` event, one
    row per step, so a run can be replayed in order and studied afterwards.
    ``kind`` is an open string (drivers/steps.py lists the values in use).
    ``content`` is redacted and capped at write time; ``properties`` carries
    ``original_chars`` when it was cut, plus ``ref``/``is_error``.
    """

    __tablename__ = "agent_run_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[str] = mapped_column(String(64), nullable=False)
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_tasks.id", ondelete="CASCADE"), nullable=False
    )
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    driver: Mapped[str] = mapped_column(String(64), nullable=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    tool: Mapped[str | None] = mapped_column(String(128), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False, default="")
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    step_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    __table_args__ = (Index("ix_agent_run_steps_task", "tenant_id", "task_id", "attempt", "seq"),)

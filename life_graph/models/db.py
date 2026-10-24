"""The Life Graph ORM models, in one import path.

This module used to hold every model (2,555 lines by 2026-10-25). They now
live by domain in ``models/memory.py``, ``models/tenancy.py``,
``models/agents.py`` and ``models/judgment.py``, with ``Base`` and the shared
helpers in ``models/base.py``. Everything is re-exported here, so
``from life_graph.models.db import Memory`` keeps working and ``Base.metadata``
sees every table once this module is imported.

All models use mapped_column style with UUID primary keys, JSONB for
schema-less properties, and pgvector for embeddings. Multi-tenant: every
model has a `tenant_id` column."""

from __future__ import annotations

from life_graph.models.agents import (
    AdvisorSession,
    AgentMessage,
    AgentPersona,
    AgentRunStep,
    AgentSession,
    AgentTask,
    Approval,
    CrossSystemSync,
    DriverStat,
    Project,
    ResearchRun,
    ScheduledJob,
    SharedContext,
    VerificationRun,
    Workflow,
    WorkflowRun,
    WorkflowStep,
    WorkflowStepRun,
)
from life_graph.models.base import _EMBED_DIM, Base, _utcnow
from life_graph.models.judgment import (
    CalibrationSnapshot,
    Challenge,
    Decision,
    Evidence,
    InterviewQuestion,
    Prediction,
    Preference,
)
from life_graph.models.memory import (
    CaptureEvent,
    Conversation,
    ConversationMessage,
    Correction,
    ExternalSession,
    Intention,
    KnowledgeGap,
    Memory,
    MemoryLink,
    MemorySession,
    Procedure,
    Session,
)
from life_graph.models.tenancy import (
    BudgetSpend,
    JobRun,
    Notification,
    PushSubscription,
    TelegramBinding,
    TelegramPairingCode,
    TenantConfig,
    TenantUsage,
    TenantWebhook,
)

__all__ = [
    "Base",
    "_EMBED_DIM",
    "_utcnow",
    "Memory",
    "Session",
    "Intention",
    "KnowledgeGap",
    "MemorySession",
    "MemoryLink",
    "Procedure",
    "CaptureEvent",
    "Correction",
    "Conversation",
    "ConversationMessage",
    "ExternalSession",
    "JobRun",
    "TenantUsage",
    "BudgetSpend",
    "TenantConfig",
    "TenantWebhook",
    "Notification",
    "PushSubscription",
    "TelegramBinding",
    "TelegramPairingCode",
    "AgentSession",
    "AgentPersona",
    "AgentTask",
    "ScheduledJob",
    "Project",
    "AdvisorSession",
    "ResearchRun",
    "AgentMessage",
    "CrossSystemSync",
    "Workflow",
    "WorkflowStep",
    "WorkflowRun",
    "WorkflowStepRun",
    "SharedContext",
    "Approval",
    "DriverStat",
    "VerificationRun",
    "AgentRunStep",
    "Preference",
    "Evidence",
    "InterviewQuestion",
    "Decision",
    "Prediction",
    "CalibrationSnapshot",
    "Challenge",
]

# NOTE: The Era-8 autonomy models (AutoAction, ApprovalQueueEntry, AuditLogEntry,
# AutonomyLevel, TrustScore, ActionSafetyRule, ShadowEnrollment, ShadowRun) live in
# life_graph/autonomy/models.py and must be imported from there directly. Do NOT
# re-export them here at module level: autonomy/models.py imports Base/_utcnow from
# this module, so a top-level `from life_graph.autonomy.models import ...` would create
# an import-order-dependent circular import. Downstream code uses function-local imports
# from life_graph.autonomy.models instead.

"""Pydantic v2 schemas for the Life Graph API layer.

All response schemas use ``from_attributes=True`` so they can be
constructed directly from SQLAlchemy ORM model instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Memory ────────────────────────────────────────────────────────────────────


class MemoryCreate(BaseModel):
    """Payload for creating a new memory."""

    content: str = Field(..., min_length=1, description="The memory content text")
    reasoning: str | None = Field(None, description="Why this memory was captured")
    tags: list[str] | None = Field(None, description="Free-form tags for categorization")
    properties: dict[str, Any] | None = Field(
        None, description="Schema-less JSONB properties"
    )
    importance: float | None = Field(
        None, ge=0.0, le=1.0, description="Importance score 0–1"
    )
    source_type: str | None = Field(None, description="e.g. explicit, inferred, cold_start")
    skip_dedup: bool = Field(False, description="Skip deduplication check on ingest")


class MemoryUpdate(BaseModel):
    """Payload for updating an existing memory (partial update)."""

    content: str | None = Field(None, min_length=1)
    reasoning: str | None = None
    tags: list[str] | None = None
    properties: dict[str, Any] | None = None
    importance: float | None = Field(None, ge=0.0, le=1.0)
    status: str | None = None


class MemoryResponse(BaseModel):
    """Serialized memory returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    reasoning: str | None = None
    tags: list[str] | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    importance: float
    confidence: float
    source_type: str
    created_at: datetime
    status: str
    access_count: int
    # ── Provenance (Feature 3) ────────────────────────────────
    extraction_tier: str | None = None
    extraction_confidence: float | None = None
    last_accessed: datetime | None = None
    supersedes: uuid.UUID | None = None
    superseded_by: uuid.UUID | None = None
    # ── Confidence Decay (Feature 4) ──────────────────────────
    reinforced_count: int = 0
    last_reinforced: datetime | None = None
    # ── Impact Scoring (Feature 5) ────────────────────────────
    impact_score: float = 0.5
    needs_verification: bool = False

    def model_post_init(self, __context: Any) -> None:
        """Compute needs_verification if not explicitly set."""
        if not self.needs_verification and self.confidence > 0:
            try:
                import math
                anchor = self.last_reinforced or self.created_at
                if anchor.tzinfo is None:
                    from datetime import timezone as tz
                    anchor = anchor.replace(tzinfo=tz.utc)
                now = datetime.now(anchor.tzinfo or __import__('datetime').timezone.utc)
                days = max((now - anchor).total_seconds() / 86400.0, 0.0)
                adj_rate = 0.03 / max(1 + self.reinforced_count * 0.5, 1.0)
                eff_conf = self.confidence * math.exp(-adj_rate * days)
                self.needs_verification = eff_conf < 0.4
            except Exception:
                pass


# ── Session ───────────────────────────────────────────────────────────────────


class SessionCreate(BaseModel):
    """Payload for starting a new session."""

    context: dict[str, Any] | None = Field(
        None, description="Initial session context (tool, project, etc.)"
    )


class SessionResponse(BaseModel):
    """Serialized session returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None = None
    context: dict[str, Any] | None = None
    summary: str | None = None
    memories_created: int
    outcome: str | None = None


class MicroConsolidationResponse(BaseModel):
    """Result from a micro-consolidation run."""

    session_id: str
    memories_processed: int = 0
    duplicates_removed: int = 0
    importance_updated: int = 0
    entities_discovered: int = 0
    edges_created: int = 0
    duration_seconds: float = 0.0


# ── Procedure (Strategy Memory) ───────────────────────────────────────────────


class ProcedureCreate(BaseModel):
    """Payload for creating a new procedure."""

    trigger: str = Field(..., min_length=1, description="When this procedure should activate")
    steps: list[str] = Field(..., min_items=1, description="Ordered list of steps")
    description: str | None = Field(None, description="Human-readable summary")
    confidence: float = Field(0.5, ge=0.0, le=1.0)
    tags: list[str] | None = None
    learned_from: list[str] | None = Field(None, description="Session IDs that led to this pattern")


class ProcedureUpdate(BaseModel):
    """Payload for updating a procedure."""

    trigger: str | None = None
    steps: list[str] | None = None
    description: str | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    status: str | None = None


class ProcedureResponse(BaseModel):
    """Serialized procedure returned by the API."""

    model_config = {"from_attributes": True}

    id: Any
    trigger: str
    steps: Any  # JSONB → list[str]
    description: str | None = None
    confidence: float = 0.5
    learned_from: Any = []  # JSONB → list[str]
    times_applied: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    tags: list[str] | None = None
    status: str = "active"
    created_at: Any = None
    updated_at: Any = None


# ── Memory Links ──────────────────────────────────────────────────────────────


class MemoryLinkCreate(BaseModel):
    """Payload for creating a link between two memories."""

    source_memory_id: str = Field(..., description="Source memory UUID (ignored in path-based routes)")
    target_memory_id: str = Field(..., description="Target memory UUID")
    link_type: str = Field(
        ...,
        pattern="^(BECAUSE|EVIDENCED_BY|RELATED_TO|CONTRADICTS|SUPERSEDES|LEADS_TO)$",
        description="Relationship type",
    )
    strength: float = Field(0.5, ge=0.0, le=1.0, description="Link strength (0.0–1.0)")


class MemoryLinkResponse(BaseModel):
    """Serialized memory link returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: Any
    source_memory_id: Any
    target_memory_id: Any
    link_type: str
    strength: float
    created_at: Any = None

    def model_post_init(self, __context: Any) -> None:
        """Convert UUID fields to strings."""
        self.id = str(self.id) if self.id else ""
        self.source_memory_id = str(self.source_memory_id) if self.source_memory_id else ""
        self.target_memory_id = str(self.target_memory_id) if self.target_memory_id else ""
        if self.created_at is not None:
            self.created_at = str(self.created_at)


# ── Intention ─────────────────────────────────────────────────────────────────


class IntentionCreate(BaseModel):
    """Payload for creating a new intention (prospective memory)."""

    content: str = Field(..., min_length=1, description="What should be remembered to do")
    trigger_type: str | None = Field(None, description="event, time, condition")
    trigger_condition: str | None = None
    trigger_time: datetime | None = None
    context_match: dict[str, Any] | None = None
    priority: str | None = Field(None, description="low, normal, high, critical")


class IntentionResponse(BaseModel):
    """Serialized intention returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    content: str
    trigger_type: str
    status: str
    priority: str
    created_at: datetime
    expires_at: datetime | None = None


# ── Search ────────────────────────────────────────────────────────────────────


class SearchQuery(BaseModel):
    """Parameters for a semantic / filtered memory search."""

    query: str = Field(..., min_length=1, description="Natural language search query")
    filters: dict[str, Any] | None = Field(
        None, description="Optional structured filters (status, properties, etc.)"
    )
    limit: int = Field(10, ge=1, le=100, description="Max results to return")
    min_importance: float | None = Field(
        None, ge=0.0, le=1.0, description="Minimum importance threshold"
    )
    tags: list[str] | None = Field(None, description="Filter by tag overlap")
    created_after: datetime | None = Field(None, description="Only memories created after this timestamp")
    created_before: datetime | None = Field(None, description="Only memories created before this timestamp")
    source_type: str | None = Field(None, description="Filter by source type (e.g. explicit, inferred, chat)")
    status: str = Field("active", description="Memory status filter (default: active only)")
    search_mode: str = Field(
        "hybrid",
        description="Search strategy: 'vector' (cosine only), 'hybrid' (vector+BM25), 'tri_hybrid' (vector+BM25+graph)",
    )


class SearchResult(BaseModel):
    """Results of a memory search, including timing metadata."""

    memories: list[MemoryResponse]
    total_count: int
    query_time_ms: float
    search_mode: str = "vector"


# ── Proactive Recall ──────────────────────────────────────────────────────────


class RecallContext(BaseModel):
    """Bundled proactive recall payload pushed at session start.

    Groups memories by purpose so the agent can weigh them appropriately.
    """

    identity: list[MemoryResponse] = Field(
        default_factory=list, description="Core identity / preference memories"
    )
    decisions: list[MemoryResponse] = Field(
        default_factory=list, description="Relevant past decisions"
    )
    intentions: list[IntentionResponse] = Field(
        default_factory=list, description="Pending intentions matching current context"
    )
    warnings: list[MemoryResponse] = Field(
        default_factory=list, description="Contradictions, lessons learned, caveats"
    )


# ── Preferences (Era 4 Personal AI) ──────────────────────────────────────────


class PreferenceCreate(BaseModel):
    """Payload for creating a new preference."""

    topic: str = Field(..., min_length=1, description="What the preference is about")
    choice: str = Field(..., min_length=1, description="The preferred choice or stance")
    reason: str | None = Field(None, description="Why this choice was made")
    context: str | None = Field(None, description="Context in which this preference applies")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Confidence score 0–1")
    source: str | None = Field(None, description="explicit, inferred, observed, cold_start")
    source_detail: str | None = Field(None, description="Where this preference came from")
    tags: list[str] | None = Field(None, description="Free-form tags")
    category: str | None = Field(None, description="Category grouping")
    properties: dict[str, Any] | None = Field(None, description="Schema-less metadata")


class PreferenceUpdate(BaseModel):
    """Payload for partially updating a preference."""

    choice: str | None = Field(None, min_length=1)
    reason: str | None = None
    context: str | None = None
    confidence: float | None = Field(None, ge=0.0, le=1.0)
    tags: list[str] | None = None
    category: str | None = None
    properties: dict[str, Any] | None = None
    status: str | None = None


class PreferenceResponse(BaseModel):
    """Serialized preference returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topic: str
    choice: str
    reason: str | None = None
    context: str | None = None
    confidence: float
    confidence_history: list[dict[str, Any]] = Field(default_factory=list)
    source: str
    source_detail: str | None = None
    tags: list[str] | None = None
    category: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    last_validated_at: datetime | None = None
    validated_count: int = 0
    last_challenged_at: datetime | None = None
    status: str
    created_at: datetime
    updated_at: datetime
    evidence_count: int = 0


# ── Evidence ──────────────────────────────────────────────────────────────────


class EvidenceCreate(BaseModel):
    """Payload for creating a new evidence item."""

    preference_id: uuid.UUID = Field(
        ..., description="ID of the preference this evidence supports/contradicts"
    )
    source_type: str = Field(
        ...,
        description="benchmark, paper, article, hn_discussion, blog, github_trend, reddit, ai_opinion",
    )
    source_url: str | None = Field(None, description="URL of the source")
    source_title: str | None = Field(None, description="Title of the source")
    stance: str = Field("supports", description="supports, contradicts, or neutral")
    summary: str = Field(..., min_length=1, description="Summary of the evidence")
    raw_content: str | None = Field(None, description="Full raw content")
    properties: dict[str, Any] | None = Field(None, description="Schema-less metadata")


class EvidenceResponse(BaseModel):
    """Serialized evidence item returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    preference_id: uuid.UUID
    source_type: str
    source_url: str | None = None
    source_title: str | None = None
    stance: str
    summary: str
    credibility: float
    weight: float
    properties: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_at: datetime


# ── Advisor ───────────────────────────────────────────────────────────────────


class AdvisorAsk(BaseModel):
    """Payload for asking the personal advisor a question."""

    question: str = Field(..., min_length=1, description="The question to ask")
    include_evidence: bool = Field(True, description="Whether to cite evidence")
    include_preferences: bool = Field(True, description="Whether to consider preferences")


class AdvisorResponse(BaseModel):
    """Response from the personal advisor."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    answer: str | None = None
    reasoning: str | None = None
    sources_used: list[dict[str, Any]] = Field(default_factory=list)
    preferences_cited: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.5
    consensus_score: float | None = None
    status: str
    created_at: datetime
    answered_at: datetime | None = None


# ── Transcript Ingestion ──────────────────────────────────────────────────────


class TranscriptIngest(BaseModel):
    """Payload for ingesting a conversation transcript to extract preferences."""

    text: str = Field(..., min_length=1, description="Raw transcript text")
    source: str = Field("conversation", description="Source label")
    context: dict[str, Any] | None = Field(None, description="Context metadata")


class TranscriptResult(BaseModel):
    """Result of transcript ingestion."""

    preferences_created: int = 0
    preferences_updated: int = 0
    evidence_added: int = 0
    details: list[dict[str, Any]] = Field(default_factory=list)


# ── Research ──────────────────────────────────────────────────────────────────


class ResearchTrigger(BaseModel):
    """Payload for triggering a research run."""

    query: str = Field(..., min_length=1, description="Research query")
    preference_ids: list[uuid.UUID] | None = Field(
        None, description="Specific preferences to research"
    )
    sources: list[str] | None = Field(None, description="Source types to search")
    max_results: int = Field(10, ge=1, le=50, description="Max evidence items to collect")


# ── Agent Tasks ───────────────────────────────────────────────────────────────


class AgentTaskCreate(BaseModel):
    """Payload for creating an agent task."""

    task_name: str | None = Field(None, description="Human-readable task label")
    agent_name: str = Field(..., description="Agent to execute this task")
    title: str | None = Field(None, max_length=200, description="Task title")
    description: str | None = Field(None, description="Detailed description")
    task_type: str = Field("general", max_length=30, description="Task type category")
    instructions: str | None = Field(None, description="Execution instructions for the agent")
    assigned_agent: str | None = Field(None, max_length=64, description="Agent assigned to execute")
    priority: str = Field("normal", description="low|normal|high|critical")
    input: dict[str, Any] | None = Field(None, description="Task input payload")
    parent_task_id: uuid.UUID | None = Field(None, description="Parent task if subtask")
    root_task_id: uuid.UUID | None = Field(None, description="Root of task tree")
    on_child_failure: str = Field("continue", max_length=20, description="continue|abort|retry")
    timeout_seconds: int = Field(300, ge=1, description="Timeout in seconds")
    max_retries: int = Field(2, ge=0, description="Maximum retry attempts")
    deadline: datetime | None = Field(None, description="Hard deadline for task completion")
    project_id: uuid.UUID | None = Field(None, description="Associated project")
    session_id: uuid.UUID | None = Field(None, description="Associated session")
    workflow_run_id: uuid.UUID | None = Field(None, description="Workflow run if part of workflow")
    workflow_step_id: uuid.UUID | None = Field(None, description="Workflow step if part of workflow")
    properties: dict[str, Any] | None = Field(None, description="Extensible JSONB properties")
    tags: list[str] | None = Field(None, description="Searchable tags")


class AgentTaskUpdate(BaseModel):
    """Partial update for an agent task."""

    status: str | None = Field(None, description="New status")
    priority: str | None = Field(None, description="Updated priority")
    assigned_agent: str | None = Field(None, max_length=64, description="Reassign to agent")
    title: str | None = Field(None, max_length=200, description="Updated title")
    description: str | None = Field(None, description="Updated description")
    instructions: str | None = Field(None, description="Updated instructions")
    result: dict[str, Any] | None = Field(None, description="Task result payload")
    error: str | None = Field(None, description="Error message if failed")
    cancel_reason: str | None = Field(None, description="Reason for cancellation")
    on_child_failure: str | None = Field(None, max_length=20, description="Updated child failure policy")
    deadline: datetime | None = Field(None, description="Updated deadline")
    properties: dict[str, Any] | None = Field(None, description="Updated properties")
    tags: list[str] | None = Field(None, description="Updated tags")


class AgentTaskResponse(BaseModel):
    """Full agent task response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    task_name: str | None = None
    agent_name: str
    title: str | None = None
    description: str | None = None
    task_type: str = "general"
    instructions: str | None = None
    assigned_agent: str | None = None
    created_by_agent: str | None = None
    status: str
    priority: str
    input: dict[str, Any] = {}
    result: dict[str, Any] = {}
    error: str | None = None
    logs: list[Any] = []
    token_usage: dict[str, Any] = {}
    model_used: str | None = None
    timeout_seconds: int
    retry_count: int
    max_retries: int
    parent_task_id: uuid.UUID | None = None
    root_task_id: uuid.UUID | None = None
    depth: int = 0
    on_child_failure: str = "continue"
    status_history: list[Any] = []
    cancel_reason: str | None = None
    session_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    claimed_at: datetime | None = None
    deadline: datetime | None = None
    source_message_id: uuid.UUID | None = None
    workflow_run_id: uuid.UUID | None = None
    workflow_step_id: uuid.UUID | None = None
    properties: dict[str, Any] = {}
    tags: list[str] | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentTaskTree(BaseModel):
    """Recursive task tree node."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_name: str | None = None
    title: str | None = None
    agent_name: str
    assigned_agent: str | None = None
    status: str
    depth: int = 0
    children: list["AgentTaskTree"] = Field(default_factory=list)


# ── Agent Messages ────────────────────────────────────────────────────────────


class AgentMessageCreate(BaseModel):
    """Payload for sending an inter-agent message."""

    sender_agent: str = Field(..., max_length=64, description="Sending agent identifier")
    recipient_agent: str = Field(..., max_length=64, description="Receiving agent identifier")
    message_type: str = Field(..., max_length=30, description="Message type")
    subject: str | None = Field(None, max_length=200, description="Message subject")
    body: str | None = Field(None, description="Message body text")
    payload: dict[str, Any] | None = Field(None, description="Structured payload")
    attachments: list[Any] | None = Field(None, description="Attachment list")
    priority: str = Field("medium", description="low|medium|high|urgent")
    thread_id: uuid.UUID | None = Field(None, description="Thread to add message to")
    reply_to_id: uuid.UUID | None = Field(None, description="Message being replied to")
    task_id: uuid.UUID | None = Field(None, description="Associated task")
    expires_at: datetime | None = Field(None, description="Message expiration time")
    properties: dict[str, Any] | None = Field(None, description="Extensible properties")


class AgentMessageResponse(BaseModel):
    """Full agent message response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    sender_agent: str
    recipient_agent: str
    thread_id: uuid.UUID | None = None
    reply_to_id: uuid.UUID | None = None
    message_type: str
    subject: str | None = None
    body: str | None = None
    payload: dict[str, Any] = {}
    attachments: list[Any] = []
    status: str
    priority: str
    task_id: uuid.UUID | None = None
    created_at: datetime
    read_at: datetime | None = None
    expires_at: datetime | None = None
    properties: dict[str, Any] = {}


class MessageReply(BaseModel):
    """Payload for replying to a message."""

    body: str | None = Field(None, description="Reply body text")
    payload: dict[str, Any] | None = Field(None, description="Structured reply payload")
    message_type: str = Field("reply", max_length=30, description="Reply message type")


# ── Cross-System Sync ─────────────────────────────────────────────────────────


class CrossSystemSyncCreate(BaseModel):
    """Payload for creating a sync operation."""

    direction: str = Field(..., max_length=20, description="push|pull|bidirectional")
    sync_type: str = Field(..., max_length=40, description="Type of sync operation")
    target_system: str = Field(..., max_length=40, description="Target system identifier")
    endpoint_url: str | None = Field(None, description="Target endpoint URL")
    request_payload: dict[str, Any] | None = Field(None, description="Request payload")
    properties: dict[str, Any] | None = Field(None, description="Extensible properties")


class CrossSystemSyncResponse(BaseModel):
    """Full sync operation response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    direction: str
    sync_type: str
    target_system: str
    endpoint_url: str | None = None
    status: str
    records_sent: int = 0
    records_synced: int = 0
    records_failed: int = 0
    sync_duration_ms: int | None = None
    error: str | None = None
    retry_count: int = 0
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    next_retry_at: datetime | None = None
    request_payload: dict[str, Any] | None = None
    response_summary: dict[str, Any] | None = None
    properties: dict[str, Any] | None = None


# ── Workflows ─────────────────────────────────────────────────────────────────


class WorkflowCreate(BaseModel):
    """Payload for creating a workflow definition."""

    name: str = Field(..., max_length=128, description="Workflow name")
    description: str | None = Field(None, description="Workflow description")
    created_by: str | None = Field(None, max_length=64, description="Creator agent")
    properties: dict[str, Any] | None = Field(None, description="Extensible properties")
    tags: list[str] | None = Field(None, description="Workflow tags")
    steps: list[dict[str, Any]] | None = Field(None, description="Workflow step definitions")


class WorkflowResponse(BaseModel):
    """Full workflow response with steps."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    name: str
    description: str | None = None
    version: int = 1
    is_active: bool = True
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime
    properties: dict[str, Any] | None = None
    tags: list[str] | None = None


class WorkflowRunTrigger(BaseModel):
    """Payload for triggering a workflow run."""

    trigger: str = Field("manual", max_length=40, description="Trigger source")
    triggered_by: str | None = Field(None, max_length=64, description="Agent that triggered the run")
    input_params: dict[str, Any] | None = Field(None, description="Input parameters")
    properties: dict[str, Any] | None = Field(None, description="Extensible properties")


class WorkflowRunResponse(BaseModel):
    """Full workflow run response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_id: uuid.UUID
    tenant_id: str
    status: str
    trigger: str
    triggered_by: str | None = None
    input_params: dict[str, Any] | None = None
    output_summary: dict[str, Any] | None = None
    properties: dict[str, Any] | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None


class WorkflowStepRunResponse(BaseModel):
    """Full workflow step run response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workflow_run_id: uuid.UUID
    workflow_step_id: uuid.UUID
    status: str
    skip_reason: str | None = None
    agent_task_id: uuid.UUID | None = None
    output: dict[str, Any] | None = None
    error: str | None = None
    attempt: int = 1
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    properties: dict[str, Any] | None = None


# ── Shared Context ────────────────────────────────────────────────────────────


class SharedContextCreate(BaseModel):
    """Payload for creating shared context."""

    title: str = Field(..., max_length=200, description="Context title")
    content: str = Field(..., min_length=1, description="Context content")
    content_type: str = Field("finding", max_length=30, description="finding|decision|artifact|note")
    project_id: str | None = Field(None, max_length=128, description="Associated project")
    source_task_id: uuid.UUID | None = Field(None, description="Task that produced this context")
    source_agent: str | None = Field(None, max_length=64, description="Agent that produced this context")
    tags: list[str] | None = Field(None, description="Searchable tags")
    relevance_score: float = Field(1.0, ge=0.0, le=1.0, description="Relevance score 0–1")
    properties: dict[str, Any] | None = Field(None, description="Extensible properties")


class SharedContextResponse(BaseModel):
    """Full shared context response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    project_id: str | None = None
    source_task_id: uuid.UUID | None = None
    source_agent: str | None = None
    title: str
    content: str
    content_type: str
    tags: list[str] | None = None
    relevance_score: float = 1.0
    access_count: int = 0
    content_hash: str | None = None
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime | None = None
    properties: dict[str, Any] | None = None


class SharedContextSearch(BaseModel):
    """Parameters for searching shared context."""

    query: str | None = Field(None, description="Text query for semantic search")
    content_type: str | None = Field(None, max_length=30, description="Filter by content type")
    project_id: str | None = Field(None, max_length=128, description="Filter by project")
    source_agent: str | None = Field(None, max_length=64, description="Filter by source agent")
    tags: list[str] | None = Field(None, description="Filter by tags (any match)")
    min_relevance: float | None = Field(None, ge=0.0, le=1.0, description="Minimum relevance score")
    limit: int = Field(20, ge=1, le=100, description="Max results to return")


# ── Capture Spine ─────────────────────────────────────────────────────────────


class CaptureEventCreate(BaseModel):
    """Payload for ingesting a capture event."""

    surface: str = Field(
        ..., description="Source surface: orchestrator|mcp|cli|voice|tool|watcher|git"
    )
    content: str = Field(..., min_length=1, description="Raw content to capture")
    modality: str = Field(default="text", description="text|voice|image|structured")
    occurred_at: datetime | None = Field(
        default=None, description="When the event occurred (defaults to now)"
    )
    properties: dict[str, Any] = Field(default_factory=dict)


class CaptureEventResponse(BaseModel):
    """Serialized capture event returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    surface: str
    modality: str
    content: str
    content_hash: str
    status: str
    yield_count: int
    occurred_at: datetime
    properties: dict[str, Any]
    created_at: datetime


class CorrectionCreate(BaseModel):
    """Payload for recording a user correction."""

    capture_event_id: uuid.UUID | None = None
    kind: str = Field(..., description="edit|override|reject|approve")
    original: str | None = None
    corrected: str | None = None
    diff_summary: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    domain_tags: list[str] = Field(default_factory=list)


class CorrectionResponse(BaseModel):
    """Serialized correction returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    capture_event_id: uuid.UUID | None
    kind: str
    original: str | None
    corrected: str | None
    diff_summary: str | None
    context: dict[str, Any]
    domain_tags: list[str]
    created_at: datetime


class InterviewQuestionResponse(BaseModel):
    """Serialized interview question returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    question: str
    origin: str
    priority: float
    status: str
    asked_count: int
    expires_at: datetime | None
    created_at: datetime


# ── Judgment Engine ─────────────────────────────────────────────────────────


class DecisionCreate(BaseModel):
    """Payload for creating a new decision."""

    title: str = Field(..., min_length=1, description="Decision title")
    reasoning: str | None = Field(default=None, description="Why this decision was made")
    options: list[dict[str, Any]] = Field(
        default_factory=list, description="[{label, pros, cons}]"
    )
    chosen_option: str | None = Field(default=None, description="Selected option")
    status: str = Field(default="decided", description="candidate|decided")
    source: str = Field(default="explicit", description="conversation|explicit|challenge")
    domain_tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.5, ge=0, le=1)
    capture_event_id: uuid.UUID | None = None
    review_at: datetime | None = None


class DecisionResponse(BaseModel):
    """Serialized decision returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    title: str
    reasoning: str | None
    options: list[dict[str, Any]]
    chosen_option: str | None
    status: str
    source: str | None
    domain_tags: list[str]
    importance: float
    capture_event_id: uuid.UUID | None
    superseded_by: uuid.UUID | None
    decided_at: datetime | None
    review_at: datetime | None
    reviewed_at: datetime | None
    properties: dict[str, Any]
    created_at: datetime


class PredictionCreate(BaseModel):
    """Payload for creating a new prediction."""

    decision_id: uuid.UUID | None = None
    statement: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.5, le=0.99, description="Confidence [0.5, 0.99]")
    domain_tags: list[str] = Field(default_factory=list)
    resolve_by: datetime | None = None
    resolution_criteria: dict[str, Any] = Field(default_factory=dict)
    capture_event_id: uuid.UUID | None = None


class PredictionResponse(BaseModel):
    """Serialized prediction returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    decision_id: uuid.UUID | None
    statement: str
    confidence: float
    domain_tags: list[str]
    resolve_by: datetime | None
    resolution_criteria: dict[str, Any]
    outcome: str
    resolved_at: datetime | None
    resolution_source: str | None
    resolution_evidence: dict[str, Any]
    actual_vs_predicted: float | None
    capture_event_id: uuid.UUID | None
    created_at: datetime


class CalibrationResponse(BaseModel):
    """Serialized calibration snapshot returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    domain: str | None
    window_days: int
    resolved_count: int
    brier_score: float | None
    buckets: list[dict[str, Any]]
    estimate_multiplier: float | None
    bias_findings: list[dict[str, Any]]
    computed_at: datetime


class ChallengeCreate(BaseModel):
    """Payload for creating a challenge (adversarial analysis)."""

    proposal: str = Field(..., min_length=1, description="What you're considering doing")


class ChallengeResponse(BaseModel):
    """Serialized challenge returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    proposal: str
    report: dict[str, Any]
    verdict: str | None
    action_taken: str | None
    total_cost_usd: float
    created_at: datetime


class PredictionResolveRequest(BaseModel):
    """Payload for resolving a prediction outcome."""

    outcome: str = Field(
        ..., description="Resolution outcome: correct|incorrect|ambiguous"
    )
    source: str = Field(..., description="Resolution source identifier")
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Supporting evidence"
    )


class ChallengeRequest(BaseModel):
    """Payload for creating an adversarial challenge."""

    proposal: str = Field(
        ..., min_length=1, description="What you're considering doing"
    )


class ChallengeResolveRequest(BaseModel):
    """Payload for recording the action taken on a challenge."""

    action_taken: str = Field(
        ..., description="What the user did: followed|ignored|modified"
    )


class JudgmentStatsResponse(BaseModel):
    """Dashboard summary statistics for the judgment engine."""

    total_decisions: int = 0
    pending_predictions: int = 0
    resolved_predictions: int = 0
    avg_brier: float | None = None
    sufficient_data: bool = False


# ── Agent Drivers ────────────────────────────────────────────────────────────


class DriverInfoResponse(BaseModel):
    """Driver availability and capability info."""

    name: str
    available: bool
    capabilities: list[str]
    cost_per_task: float


class DriverStatsResponse(BaseModel):
    """Aggregated driver statistics for a time window."""

    model_config = ConfigDict(from_attributes=True)

    driver: str
    task_type: str | None
    dispatched: int
    verified_landed: int
    failed: int
    total_cost_usd: float
    success_rate: float
    cost_per_verified: float


class VerificationRunResponse(BaseModel):
    """Serialized verification run returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID | None
    attempt: int
    passed: bool
    results: list[dict[str, Any]]
    created_at: datetime

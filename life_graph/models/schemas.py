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


class SearchResult(BaseModel):
    """Results of a memory search, including timing metadata."""

    memories: list[MemoryResponse]
    total_count: int
    query_time_ms: float


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

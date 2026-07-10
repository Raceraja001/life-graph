"""Pydantic v2 schemas for the Watcher API layer (Era 6 Ambient AI).

All response schemas use ``from_attributes=True`` so they can be
constructed directly from SQLAlchemy ORM model instances.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ── Watch Config ──────────────────────────────────────────────────────────────


class WatchConfigResponse(BaseModel):
    """Serialized watcher configuration returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    watcher_name: str
    enabled: bool = True
    schedule: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class WatchConfigUpdate(BaseModel):
    """Payload for updating a watcher configuration."""

    enabled: bool | None = None
    schedule: str | None = None
    config: dict[str, Any] | None = None


# ── Watch Events ──────────────────────────────────────────────────────────────


class WatchEventResponse(BaseModel):
    """Serialized watch event returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    watcher_name: str | None = None
    severity: str
    title: str
    details: str | None = None
    acknowledged: bool = False
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    retry_count: int = 0
    run_id: uuid.UUID | None = None
    created_at: datetime


class WatchEventSummary(BaseModel):
    """Aggregated event counts by severity and watcher."""

    total: int = 0
    by_severity: dict[str, int] = Field(default_factory=dict)
    by_watcher: dict[str, int] = Field(default_factory=dict)
    unacknowledged: int = 0


class AcknowledgeRequest(BaseModel):
    """Payload for acknowledging a single event."""

    acknowledged_by: str | None = Field(None, description="Who acknowledged this event")


class BulkAcknowledgeRequest(BaseModel):
    """Payload for bulk-acknowledging events."""

    event_ids: list[uuid.UUID] | None = Field(None, description="Specific event IDs (or all if omitted)")
    watcher_name: str | None = Field(None, description="Filter by watcher name")
    severity: str | None = Field(None, description="Filter by severity")
    acknowledged_by: str | None = Field(None, description="Who acknowledged these events")


# ── Watcher Runs ──────────────────────────────────────────────────────────────


class WatcherRunResponse(BaseModel):
    """Serialized watcher run record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    watcher_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    events_created: int = 0
    error: str | None = None
    duration_ms: float | None = None


# ── Tech Radar ────────────────────────────────────────────────────────────────


class TechRadarResponse(BaseModel):
    """Serialized tech radar article returned by the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    source: str | None = None
    title: str
    url: str | None = None
    summary: str | None = None
    relevance_score: float = 0.0
    tags: list[str] | None = None
    published_at: datetime | None = None
    created_at: datetime


class TechRadarQuery(BaseModel):
    """Query params for tech radar search."""

    source: str | None = None
    min_score: float | None = Field(None, ge=0.0, le=1.0)
    days: int | None = Field(None, ge=1)
    limit: int = Field(20, ge=1, le=100)


# ── Notification Channels ────────────────────────────────────────────────────


class NotificationChannelCreate(BaseModel):
    """Payload for creating a notification channel."""

    channel_type: str = Field(
        ...,
        description="Channel type: email, webhook, terminal",
    )
    name: str | None = Field(None, description="Human-readable name")
    config: dict[str, Any] = Field(default_factory=dict, description="Channel config (SMTP, URL, etc.)")
    priority: int = Field(0, description="Higher = preferred. Primary channel has highest priority.")
    enabled: bool = True


class NotificationChannelResponse(BaseModel):
    """Serialized notification channel."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    channel_type: str
    name: str | None = None
    config: dict[str, Any] = Field(default_factory=dict)
    priority: int = 0
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class NotificationChannelUpdate(BaseModel):
    """Payload for updating a notification channel."""

    name: str | None = None
    config: dict[str, Any] | None = None
    priority: int | None = None
    enabled: bool | None = None


# ── Notifications ─────────────────────────────────────────────────────────────


class NotificationResponse(BaseModel):
    """Serialized notification record."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    event_id: uuid.UUID | None = None
    channel_type: str | None = None
    title: str | None = None
    body: str | None = None
    severity: str | None = None
    status: str = "pending"
    sent_at: datetime | None = None
    created_at: datetime

"""Pydantic v2 schemas for the Watcher API layer (Era 6 Ambient AI).

All response schemas use ``from_attributes=True`` so they can be
constructed directly from SQLAlchemy ORM model instances.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
)

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
    """Serialized watch event returned by the API.

    ``acknowledged`` is derived, not stored: WatchEvent records the fact as
    ``acknowledged_at``. It was previously a plain field with a False default,
    which from_attributes could never populate — so an acknowledged event kept
    reporting ``acknowledged: false`` and the UI kept showing it as pending.

    A ``retry_count`` field used to sit here too. WatchEvent has no such
    column — the retry counter belongs to WatcherNotification, which is where
    deliveries are tracked — so it reported 0 for every event regardless.
    Removed rather than aliased: there is no per-event retry count to report.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    tenant_id: str
    watcher_name: str | None = None
    severity: str
    title: str
    details: str | None = None
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None
    run_id: uuid.UUID | None = None
    created_at: datetime

    @computed_field
    @property
    def acknowledged(self) -> bool:
        return self.acknowledged_at is not None

    @field_validator("details", mode="before")
    @classmethod
    def _details_as_text(cls, v: Any) -> str | None:
        """WatchEvent.details is JSONB and genuinely holds either shape.

        The ad-hoc watchers store a string; BaseWatcher.emit_event() stores a
        dict. A dict reaching this ``str | None`` field raised ValidationError,
        so listing events 500'd for any event a lifecycle watcher produced —
        which is every event from dependency_watcher and tech_radar now that
        both are registered. Rendered to text here for a stable wire contract,
        matching how notification bodies are handled.
        """
        if v is None or isinstance(v, str):
            return v
        try:
            return json.dumps(v, default=str)
        except (TypeError, ValueError):
            return str(v)


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

    event_ids: list[uuid.UUID] | None = Field(
        None, description="Specific event IDs (or all if omitted)"
    )
    watcher_name: str | None = Field(None, description="Filter by watcher name")
    severity: str | None = Field(None, description="Filter by severity")
    acknowledged_by: str | None = Field(None, description="Who acknowledged these events")


# ── Watcher Runs ──────────────────────────────────────────────────────────────


class WatcherRunResponse(BaseModel):
    """Serialized watcher run record.

    ``events_created`` is the wire name; the column is ``events_generated``.
    Without the alias, from_attributes found no such attribute and fell back
    to the default, so every run reported 0 events regardless of what it did.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    tenant_id: str
    watcher_name: str
    status: str
    started_at: datetime
    completed_at: datetime | None = None
    events_created: int = Field(
        default=0, validation_alias=AliasChoices("events_generated", "events_created")
    )
    error: str | None = None
    duration_ms: float | None = None


# ── Tech Radar ────────────────────────────────────────────────────────────────


class TechRadarResponse(BaseModel):
    """Serialized tech radar article returned by the API.

    Three of these fields named nothing on TechRadarItem. ``created_at`` was
    required with no counterpart, so this endpoint returned 200 while the
    table was empty and 500 the moment it held a single row. ``relevance_score``
    is the ``score`` column and ``created_at`` is ``scraped_at``; both keep
    their wire names via aliases.

    A ``published_at`` field is gone. TechRadarItem records when an item was
    scraped, never when it was published, so the field could only ever be
    null — aliasing it to scraped_at would have reported a scrape time as a
    publication time.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    tenant_id: str
    source: str | None = None
    title: str
    url: str | None = None
    summary: str | None = None
    relevance_score: float = Field(
        default=0.0, validation_alias=AliasChoices("score", "relevance_score")
    )
    tags: list[str] | None = None
    created_at: datetime = Field(validation_alias=AliasChoices("scraped_at", "created_at"))


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
    config: dict[str, Any] = Field(
        default_factory=dict, description="Channel config (SMTP, URL, etc.)"
    )
    priority: int = Field(
        0, description="Higher = preferred. Primary channel has highest priority."
    )
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
    """Serialized notification record.

    The wire names ``channel_type`` and ``title`` predate the table; the
    WatcherNotification columns are ``channel`` and ``subject``. The aliases
    keep the public shape stable while actually reading the model — without
    them both fields serialized as null for every row.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: uuid.UUID
    tenant_id: str
    event_id: uuid.UUID | None = None
    channel_type: str | None = Field(
        default=None, validation_alias=AliasChoices("channel", "channel_type")
    )
    title: str | None = Field(default=None, validation_alias=AliasChoices("subject", "title"))
    body: str | None = None
    severity: str | None = None
    status: str = "pending"
    sent_at: datetime | None = None
    created_at: datetime

"""Pydantic schemas for audit log."""

from __future__ import annotations

from datetime import datetime, date
from uuid import UUID

from pydantic import BaseModel, Field


class AuditEntryResponse(BaseModel):
    """Response for a single audit log entry."""

    id: UUID
    tenant_id: str
    action_type: str
    action_id: UUID | None = None
    agent_id: str | None = None
    project_id: str | None = None
    risk_level: str | None = None
    command: str | None = None
    result: str | None = None
    details: dict | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditQuery(BaseModel):
    """Query filters for audit log."""

    agent_id: str | None = None
    action_type: str | None = None
    risk_level: str | None = None
    result: str | None = None
    project_id: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    limit: int = Field(50, ge=1, le=500)
    offset: int = Field(0, ge=0)


class ExportRequest(BaseModel):
    """Request to export audit logs as NDJSON."""

    start_date: date
    end_date: date
    project_id: str | None = None

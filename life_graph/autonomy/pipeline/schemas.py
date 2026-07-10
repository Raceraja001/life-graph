"""Pydantic schemas for autonomy pipeline requests/responses."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AutoFixRequest(BaseModel):
    """Request to trigger an autonomous action."""

    agent_id: str = Field(..., description="Agent initiating the action")
    project_id: str = Field(..., description="Target project")
    action_type: str = Field(..., description="e.g. fix_lint, restart_service")
    command: str = Field(..., description="Shell command to execute")
    rollback_command: str | None = Field(None, description="Undo command")
    description: str = Field("", description="Human-readable summary")
    timeout_seconds: int = Field(60, ge=5, le=600)
    metadata: dict | None = Field(None, description="Extra context")


class AutoActionResponse(BaseModel):
    """Response for a single auto action."""

    id: UUID
    tenant_id: str
    agent_id: str
    project_id: str
    action_type: str
    command: str
    rollback_command: str | None = None
    description: str = ""
    risk_level: str
    status: str
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    duration_ms: float | None = None
    approval_id: UUID | None = None
    executed_at: datetime | None = None
    created_at: datetime
    metadata: dict | None = None

    model_config = {"from_attributes": True}


class AutoFixResponse(BaseModel):
    """Response from the auto-fix pipeline."""

    action: AutoActionResponse
    routing: str = Field(..., description="auto_executed | notify_before | queued_for_approval")
    message: str = ""

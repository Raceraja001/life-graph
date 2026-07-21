"""Pydantic schemas for autonomy pipeline requests/responses.

The request keeps a friendly external contract (``action_type`` / ``command`` /
``description``); the service maps those onto the real ``AutoAction`` columns
(``action_name`` / ``action_command`` / ``trigger_type`` / ``trigger_detail``).
The response serializes real ``AutoAction`` fields. See
docs/specs/era8-autonomy-reconciliation.md.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AutoFixRequest(BaseModel):
    """Request to trigger an autonomous action."""

    agent_id: str = Field(..., description="Agent initiating the action")
    project_id: str = Field(..., description="Target project")
    action_type: str = Field(..., description="e.g. fix_lint, restart_service")
    command: str = Field(..., description="Shell command to execute")
    rollback_command: str | None = Field(None, description="Undo command")
    description: str = Field("", description="Human-readable summary")
    timeout_seconds: int = Field(60, ge=5, le=600, description="Executor timeout (not persisted)")
    metadata: dict | None = Field(None, description="Extra context (not persisted)")


class AutoActionResponse(BaseModel):
    """Response for a single auto action (real ``AutoAction`` fields)."""

    id: str
    tenant_id: str
    agent_id: str
    project_id: str | None = None
    action_name: str
    action_command: str
    rollback_command: str | None = None
    trigger_type: str
    trigger_detail: str
    risk_level: str | None = None
    status: str
    exit_code: int | None = None
    stdout: str | None = None
    stderr: str | None = None
    error_message: str | None = None
    duration_ms: int | None = None
    approval_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AutoFixResponse(BaseModel):
    """Response from the auto-fix pipeline."""

    action: AutoActionResponse
    routing: str = Field(..., description="auto_executed | notify_before | queued_for_approval")
    message: str = ""

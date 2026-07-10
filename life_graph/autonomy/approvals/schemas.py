"""Pydantic schemas for approval queue."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalResponse(BaseModel):
    """Response for a single approval queue entry."""

    id: UUID
    tenant_id: str
    action_id: UUID
    agent_id: str
    project_id: str
    action_type: str
    risk_level: str
    command: str
    description: str = ""
    status: str
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    decision_note: str | None = None
    expires_at: datetime | None = None
    escalation_level: int = 0
    created_at: datetime

    model_config = {"from_attributes": True}


class ResolveRequest(BaseModel):
    """Request to resolve (approve/reject) an approval."""

    decision: str = Field(..., pattern="^(approve|reject)$")
    note: str | None = Field(None, max_length=500)
    resolved_by: str = Field(..., description="Who is resolving")
    also_trust: bool = Field(False, description="Also update trust score")


class BatchResolveRequest(BaseModel):
    """Request to batch resolve approvals."""

    approval_ids: list[UUID] | None = Field(None, description="Specific IDs, or use filters")
    agent_id: str | None = None
    project_id: str | None = None
    risk_level: str | None = None
    decision: str = Field(..., pattern="^(approve|reject)$")
    note: str | None = Field(None, max_length=500)
    resolved_by: str = Field(...)


class BatchResolveResponse(BaseModel):
    """Response from batch resolve."""

    resolved_count: int
    resolved_ids: list[UUID]

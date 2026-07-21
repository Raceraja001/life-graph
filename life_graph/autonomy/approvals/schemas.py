"""Pydantic schemas for the Era-8 autonomy approval queue.

Aligned to the real ``ApprovalQueueEntry`` model (table ``approval_queue``).
See docs/specs/era8-autonomy-reconciliation.md.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ApprovalResponse(BaseModel):
    """Response for a single approval queue entry (real fields)."""

    id: str
    tenant_id: str
    agent_id: str
    project_id: str | None = None
    action_name: str
    action_command: str
    risk_level: str | None = None
    category: str = "general"
    trigger_type: str
    trigger_detail: str
    estimated_impact: str | None = None
    status: str
    priority: int = 100
    resolved_by: str | None = None
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    expires_at: datetime | None = None
    timeout_hours: int = 24
    escalation_sent: list = Field(default_factory=list)
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

    approval_ids: list[str] | None = Field(None, description="Specific IDs, or use filters")
    agent_id: str | None = None
    project_id: str | None = None
    risk_level: str | None = None
    decision: str = Field(..., pattern="^(approve|reject)$")
    note: str | None = Field(None, max_length=500)
    resolved_by: str = Field(...)


class BatchResolveResponse(BaseModel):
    """Response from batch resolve."""

    resolved_count: int
    resolved_ids: list[str]

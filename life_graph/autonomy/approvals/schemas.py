"""Pydantic schemas for the Era-8 autonomy approval queue.

Aligned to the real ``ApprovalQueueEntry`` model (table ``approval_queue``).
See docs/specs/era8-autonomy-reconciliation.md.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


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
    # Who asked for the work (server-derived; None when not recorded).
    requested_by: str | None = None
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
    # Optional and not trusted: who resolved is the server's to say
    # (api/approval_identity.py). A value here is only kept in the note.
    resolved_by: str | None = Field(
        None, max_length=128, description="Ignored for identity; recorded as an unverified note"
    )
    # Deprecated 2026-11-20. It was accepted and silently ignored (the
    # service never read it). Changing trust is the owner's alone and has its
    # own route, POST /autonomy/trust/override; an approval does not do it on
    # the side. ``false`` (or leaving it out) is still accepted so old clients
    # keep working; ``true`` is refused rather than ignored.
    also_trust: bool = Field(
        False,
        deprecated=True,
        description=(
            "Deprecated, must be false. Use POST /autonomy/trust/override (owner only)"
            " to change trust."
        ),
    )

    @field_validator("also_trust")
    @classmethod
    def _also_trust_unsupported(cls, value: bool) -> bool:
        if value:
            raise ValueError(
                "also_trust is no longer supported: approving does not change trust."
                " Use POST /autonomy/trust/override (owner only)."
            )
        return value


class BatchResolveRequest(BaseModel):
    """Request to batch resolve approvals."""

    approval_ids: list[str] | None = Field(None, description="Specific IDs, or use filters")
    agent_id: str | None = None
    project_id: str | None = None
    risk_level: str | None = None
    # With no ids and no filter the batch would match every pending entry;
    # that now has to be asked for in so many words.
    all: bool = Field(False, description="Resolve every pending entry (needs no filter)")
    decision: str = Field(..., pattern="^(approve|reject)$")
    note: str | None = Field(None, max_length=500)
    resolved_by: str | None = Field(
        None, max_length=128, description="Ignored for identity; recorded as an unverified note"
    )

    def has_filter(self) -> bool:
        """True when ids (even an empty list) or any filter narrows the batch."""
        return self.approval_ids is not None or any(
            (self.agent_id, self.project_id, self.risk_level)
        )


class BatchResolveResponse(BaseModel):
    """Response from batch resolve."""

    resolved_count: int
    resolved_ids: list[str]
    # Entries decided through the approvals feed (they run an action) whose
    # decision did not go through: [{"id", "status_code", "error"}].
    failed: list[dict] = Field(default_factory=list)

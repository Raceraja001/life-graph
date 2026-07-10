"""Pydantic schemas for autonomy levels."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


LEVEL_DESCRIPTIONS = {
    0: "Ask Everything",
    1: "Safe Auto",
    2: "Notify Before",
    3: "Full Auto",
}


class AutonomyLevelResponse(BaseModel):
    """Response for a project's autonomy level."""

    id: UUID
    tenant_id: str
    project_id: str
    current_level: int
    level_name: str
    safe_count: int = 0
    moderate_count: int = 0
    failure_count: int = 0
    promotion_eligible: bool = False
    promotion_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SetLevelRequest(BaseModel):
    """Request to manually set autonomy level."""

    level: int = Field(..., ge=0, le=3)
    reason: str = Field(..., min_length=3, max_length=500)
    set_by: str = Field(..., description="Who is setting the level")

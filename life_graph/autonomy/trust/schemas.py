from datetime import datetime
from pydantic import BaseModel, Field


class TrustScoreResponse(BaseModel):
    """Response model for a trust score."""

    id: str
    tenant_id: str
    agent_id: str
    action_type: str
    project_id: str | None
    score: float
    total_successes: int
    total_failures: int
    consecutive_successes: int
    consecutive_failures: int
    peak_score: float
    last_action_at: datetime | None
    last_failure_at: datetime | None
    last_success_at: datetime | None
    decay_rate: float
    failure_penalty: float
    manual_override: float | None
    override_reason: str | None
    override_by: str | None
    override_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}



class TrustOverrideRequest(BaseModel):
    """Request body for manually overriding a trust score."""

    agent_id: str = Field(..., min_length=1)
    action_type: str = Field(..., min_length=1)
    project_id: str | None = None
    score: float = Field(..., ge=0.0, le=1.0)
    reason: str = Field(..., min_length=1)
    by: str = Field(..., min_length=1)

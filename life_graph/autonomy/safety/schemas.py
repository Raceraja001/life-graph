"""Pydantic schemas for safety classification API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SafetyRuleCreate(BaseModel):
    """Request body for creating a safety rule."""

    action_name: str = Field(..., min_length=1)
    action_pattern: str = Field(..., min_length=1)
    category: str = "general"
    risk_level: str = Field("dangerous", pattern=r"^(safe|moderate|dangerous)$")
    trust_threshold: float = 0.7
    is_guardrail: bool = False
    max_blast_radius: int | None = None
    requires_staging: bool = False
    is_reversible: bool = True
    rollback_template: str | None = None
    enabled: bool = True
    priority: int = 100
    description: str | None = None
    created_by: str = "manual"


class SafetyRuleUpdate(BaseModel):
    """Request body for updating a safety rule (partial)."""

    action_pattern: str | None = None
    category: str | None = None
    risk_level: str | None = Field(None, pattern=r"^(safe|moderate|dangerous)$")
    trust_threshold: float | None = None
    is_guardrail: bool | None = None
    max_blast_radius: int | None = None
    requires_staging: bool | None = None
    is_reversible: bool | None = None
    rollback_template: str | None = None
    enabled: bool | None = None
    priority: int | None = None
    description: str | None = None


from datetime import datetime
from pydantic import BaseModel


class SafetyRuleResponse(BaseModel):
    """Response model for a safety rule."""

    id: str
    tenant_id: str
    action_name: str
    action_pattern: str
    category: str
    risk_level: str
    trust_threshold: float
    is_guardrail: bool
    max_blast_radius: int | None
    requires_staging: bool
    is_reversible: bool
    rollback_template: str | None
    enabled: bool
    priority: int
    description: str | None
    created_by: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}



class ClassifyRequest(BaseModel):
    """Request body for classifying an action."""

    agent_id: str = Field(..., min_length=1)
    action_name: str = Field(..., min_length=1)
    action_command: str = Field(..., min_length=1)
    project_id: str | None = None


class ClassifyResponse(BaseModel):
    """Response model for action classification."""

    risk_level: str
    recommendation: str
    trust_score: float
    autonomy_level: str
    matched_rule_id: str | None = None
    reasoning: dict = {}

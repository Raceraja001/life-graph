"""Safety classification API router.

Endpoints for managing safety rules and classifying actions.
Prefix: /autonomy/safety
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.responses import success_response
from life_graph.autonomy.safety.classifier import ActionClassifier
from life_graph.autonomy.safety.schemas import (
    ClassifyRequest,
    ClassifyResponse,
    SafetyRuleCreate,
    SafetyRuleResponse,
    SafetyRuleUpdate,
)
from life_graph.autonomy.safety.service import SafetyRuleService
from life_graph.core.tenant import get_current_tenant_id
from life_graph.storage.database import get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/safety", tags=["autonomy-safety"])


# ── Safety Rules CRUD ─────────────────────────────────────────


@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: SafetyRuleCreate,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Create a new safety rule."""
    svc = SafetyRuleService(session)
    rule = await svc.create_rule(
        tenant_id=tenant_id,
        action_name=body.action_name,
        action_pattern=body.action_pattern,
        risk_level=body.risk_level,
        created_by=body.created_by,
        category=body.category,
        trust_threshold=body.trust_threshold,
        is_guardrail=body.is_guardrail,
        max_blast_radius=body.max_blast_radius,
        requires_staging=body.requires_staging,
        is_reversible=body.is_reversible,
        rollback_template=body.rollback_template,
        enabled=body.enabled,
        priority=body.priority,
        description=body.description,
    )
    return success_response(SafetyRuleResponse.model_validate(rule))


@router.get("/rules")
async def list_rules(
    enabled_only: bool = Query(True),
    category: str | None = Query(None),
    risk_level: str | None = Query(None),
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """List safety rules with optional filters."""
    svc = SafetyRuleService(session)
    rules = await svc.list_rules(
        tenant_id=tenant_id,
        enabled_only=enabled_only,
        category=category,
        risk_level=risk_level,
    )
    return success_response(
        [SafetyRuleResponse.model_validate(r) for r in rules]
    )


@router.get("/rules/{rule_id}")
async def get_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Get a single safety rule by ID."""
    svc = SafetyRuleService(session)
    rule = await svc.get_rule(tenant_id, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Safety rule not found")
    return success_response(SafetyRuleResponse.model_validate(rule))


@router.patch("/rules/{rule_id}")
async def update_rule(
    rule_id: str,
    body: SafetyRuleUpdate,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Update a safety rule (partial update)."""
    svc = SafetyRuleService(session)
    updates = body.model_dump(exclude_unset=True)
    rule = await svc.update_rule(tenant_id, rule_id, **updates)
    if rule is None:
        raise HTTPException(status_code=404, detail="Safety rule not found")
    return success_response(SafetyRuleResponse.model_validate(rule))


@router.delete("/rules/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_rule(
    rule_id: str,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Delete a safety rule."""
    svc = SafetyRuleService(session)
    deleted = await svc.delete_rule(tenant_id, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Safety rule not found")
    return success_response({"deleted": True})


# ── Classification ────────────────────────────────────────────


@router.post("/classify")
async def classify_action(
    body: ClassifyRequest,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Classify an action through the safety pipeline."""
    classifier = ActionClassifier(session)
    result = await classifier.classify(
        tenant_id=tenant_id,
        agent_id=body.agent_id,
        action_name=body.action_name,
        action_command=body.action_command,
        project_id=body.project_id,
    )
    return success_response(
        ClassifyResponse(
            risk_level=result.risk_level.value,
            recommendation=result.recommendation.value,
            trust_score=result.trust_score,
            autonomy_level=result.autonomy_level,
            matched_rule_id=result.matched_rule.id if result.matched_rule else None,
            reasoning=result.reasoning,
        )
    )


# ── Seed Defaults ─────────────────────────────────────────────


@router.post("/seed", status_code=status.HTTP_201_CREATED)
async def seed_defaults(
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Seed default safety rules for the current tenant."""
    svc = SafetyRuleService(session)
    rules = await svc.seed_defaults(tenant_id)
    return success_response(
        [SafetyRuleResponse.model_validate(r) for r in rules]
    )

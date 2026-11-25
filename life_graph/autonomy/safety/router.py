"""Safety classification API router.

Endpoints for managing safety rules and classifying actions.
Prefix: /autonomy/safety

A safety rule sets an action's risk, and risk decides whether it runs without
asking, so writing rules (create, update, delete, seed the defaults) is the
owner's alone (api/approval_identity.py ``owner_only``); ``created_by`` is who
the server saw calling. So is resuming autonomy after the kill switch was
pulled. Pausing stays open to any caller — stopping is always safe — and so
do the reads and ``/classify``, which writes nothing.

Every rule write leaves one audit_log row (``rule_change``) naming who made
it. The change is committed first; the audit row is best effort, as for the
kill switch: if it cannot be written that is logged as an error, and the
change stands.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.api.approval_identity import owner_only, resolver
from life_graph.api.responses import success_response
from life_graph.autonomy.approvals.durable_store import StoreUnavailableError
from life_graph.autonomy.kill_switch import revoke_live_capabilities
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
from life_graph.runtime import get_audit_service
from life_graph.services.dev import tasks as dev_tasks
from life_graph.storage.database import async_session, get_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/safety", tags=["autonomy-safety"])


# ── Safety Rules CRUD ─────────────────────────────────────────


@router.post("/rules", status_code=status.HTTP_201_CREATED)
async def create_rule(
    body: SafetyRuleCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Create a new safety rule (owner only)."""
    owner_only(request, "Writing a safety rule")
    svc = SafetyRuleService(session)
    rule = await svc.create_rule(
        tenant_id=tenant_id,
        action_name=body.action_name,
        action_pattern=body.action_pattern,
        risk_level=body.risk_level,
        created_by=resolver(request),
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
    await session.commit()
    await _audit_rule_change(tenant_id, request, "create", rule.id, new=_rule_snapshot(rule))
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
    return success_response([SafetyRuleResponse.model_validate(r) for r in rules])


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
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Update a safety rule (partial update; owner only)."""
    owner_only(request, "Writing a safety rule")
    svc = SafetyRuleService(session)
    existing = await svc.get_rule(tenant_id, rule_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Safety rule not found")
    old = _rule_snapshot(existing)
    updates = body.model_dump(exclude_unset=True)
    rule = await svc.update_rule(tenant_id, rule_id, **updates)
    if rule is None:
        raise HTTPException(status_code=404, detail="Safety rule not found")
    await session.commit()
    await _audit_rule_change(
        tenant_id, request, "update", rule_id, old=old, new=_rule_snapshot(rule)
    )
    return success_response(SafetyRuleResponse.model_validate(rule))


@router.delete("/rules/{rule_id}", status_code=status.HTTP_200_OK)
async def delete_rule(
    rule_id: str,
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Delete a safety rule (owner only)."""
    owner_only(request, "Writing a safety rule")
    svc = SafetyRuleService(session)
    existing = await svc.get_rule(tenant_id, rule_id)
    old = _rule_snapshot(existing) if existing is not None else None
    deleted = await svc.delete_rule(tenant_id, rule_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Safety rule not found")
    await session.commit()
    await _audit_rule_change(tenant_id, request, "delete", rule_id, old=old)
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
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Seed default safety rules for the current tenant (owner only).

    The defaults mark some actions ``safe``; re-seeding after the owner
    removed one would make it auto-executable again.
    """
    owner_only(request, "Writing a safety rule")
    svc = SafetyRuleService(session)
    rules = await svc.seed_defaults(tenant_id)
    await session.commit()
    created = {"created": [{"id": r.id, "action_name": r.action_name} for r in rules]}
    await _audit_rule_change(tenant_id, request, "seed", new=created)
    return success_response([SafetyRuleResponse.model_validate(r) for r in rules])


def _rule_snapshot(rule) -> dict:
    """A rule as plain JSON, for the audit row's old/new value."""
    return SafetyRuleResponse.model_validate(rule).model_dump(mode="json")


async def _audit_rule_change(
    tenant_id: str,
    request: Request,
    change_type: str,
    rule_id: str | None = None,
    old: dict | None = None,
    new: dict | None = None,
) -> None:
    """One audit_log row per rule write, with who did it (the resolver).

    Called after the change is committed. Best effort: a failed audit write
    is logged and the change stands (the same choice as the kill switch).
    """
    try:
        await get_audit_service().log_rule_change(
            tenant_id=tenant_id,
            rule_id=rule_id,
            change_type=change_type,
            changed_by=resolver(request),
            old_value=old,
            new_value=new,
        )
    except Exception:
        logger.error("Safety rule %s for %s not written to the audit log", change_type, tenant_id,
                     exc_info=True)  # fmt: skip


# ── Kill Switch ──────────────────────────────────────────────
# Emergency stop for autonomous action execution (life_graph/autonomy/
# kill_switch.py, checked by AutoFixService._run_action). Scoped to the
# current tenant, not an admin-only cross-tenant control, since this is
# meant to be user-triggered.


def _kill_switch_response(config) -> dict:
    return {
        "autonomy_paused": bool(config.autonomy_paused) if config else True,
        "autonomy_paused_at": (
            config.autonomy_paused_at.isoformat() if config and config.autonomy_paused_at else None
        ),
    }


@router.get("/kill-switch")
async def get_kill_switch(
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Current autonomy kill-switch state for this tenant."""
    from life_graph.models.db import TenantConfig

    config = await session.get(TenantConfig, tenant_id)
    return success_response(_kill_switch_response(config))


@router.post("/kill-switch/pause")
async def pause_kill_switch(
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Immediately stop all autonomous action execution for this tenant.

    Then revoke the tenant's live capabilities (errand mandates), so nothing
    approved before the pause can still be spent. The pause is committed
    first and stands whatever happens next: if the capability store cannot
    be reached the answer is 503 saying exactly that — autonomy IS paused,
    the revocation did not happen, pause again to retry it (pausing is
    idempotent). A 200 that hid the failure would claim a stop that left
    mandates live; failing the pause itself would leave autonomy running.
    """
    from datetime import UTC, datetime

    from life_graph.autonomy.kill_switch import invalidate_autonomy_pause_cache
    from life_graph.models.db import TenantConfig

    config = await session.get(TenantConfig, tenant_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    config.autonomy_paused = True
    config.autonomy_paused_at = datetime.now(UTC)
    await session.commit()
    invalidate_autonomy_pause_cache(tenant_id)
    cancelled = await _cancel_running_dev_tasks(tenant_id)
    await _audit_kill_switch(tenant_id, "pause", request, {"dev_tasks_cancelled": cancelled})
    try:
        revoked = await revoke_live_capabilities(tenant_id)
    except StoreUnavailableError as exc:
        logger.error(
            "Autonomy paused for tenant %s, but revoking live capabilities failed: %s",
            tenant_id,
            exc,
        )
        raise HTTPException(
            status_code=503,
            detail=(
                "Autonomy is paused, but its live capabilities could not be revoked"
                f" ({exc}). Pause again to retry the revocation."
            ),
        ) from exc
    return success_response(
        {
            **_kill_switch_response(config),
            "capabilities_revoked": revoked,
            "dev_tasks_cancelled": cancelled,
        }
    )


async def _cancel_running_dev_tasks(tenant_id: str) -> int:
    """Stop the dev tasks already running; -1 when that could not be done.

    After the pause is committed, so it stands whatever happens here.
    """
    try:
        return await dev_tasks.cancel_running_for_tenant(async_session, tenant_id)
    except Exception:
        logger.error("Autonomy paused for %s, but cancelling its dev tasks failed", tenant_id,
                     exc_info=True)  # fmt: skip
        return -1


async def _audit_kill_switch(tenant_id: str, what: str, request: Request, details: dict) -> None:
    """One audit_log row per pause or resume, with who did it (the resolver)."""
    try:
        await get_audit_service()._append(
            tenant_id=tenant_id,
            action_type="kill_switch",
            action_name=f"autonomy_{what}",
            actor_type="operator",
            actor_id=resolver(request),
            result="success",
            details={"what": what, **details},
        )
    except Exception:
        # The audit row must not undo or block the stop itself.
        logger.error("Kill switch %s for %s not written to the audit log", what, tenant_id,
                     exc_info=True)  # fmt: skip


@router.post("/kill-switch/resume")
async def resume_kill_switch(
    request: Request,
    session: AsyncSession = Depends(get_session),
    tenant_id: str = Depends(get_current_tenant_id),
):
    """Resume autonomous action execution for this tenant (owner only)."""
    owner_only(request, "Resuming autonomy")
    from life_graph.autonomy.kill_switch import invalidate_autonomy_pause_cache
    from life_graph.models.db import TenantConfig

    config = await session.get(TenantConfig, tenant_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Tenant '{tenant_id}' not found")
    config.autonomy_paused = False
    config.autonomy_paused_at = None
    await session.commit()
    invalidate_autonomy_pause_cache(tenant_id)
    await _audit_kill_switch(tenant_id, "resume", request, {})
    return success_response(_kill_switch_response(config))

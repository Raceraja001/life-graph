"""Ambient-project startup seeding for Sub-project B (autonomous action roles).

Layers infra-specific safety rules on top of ``SafetyRuleService.seed_defaults`` — the
shell-command style actions the ``ops`` ambient-action persona proposes (``docker_ps``,
``restart_*``, ``rm *``, ...) aren't covered by the app-level defaults (``deploy_staging``,
``delete_data``, ...) — and sets the ``ambient`` project's autonomy level to L1 (Safe
Auto). Without this, every proposed action queues for approval forever: a fresh
``AutonomyLevel`` row defaults to L0 (Ask Everything).
"""

from __future__ import annotations

import logging

from sqlalchemy import select

from life_graph.autonomy.levels.service import AutonomyLevelService
from life_graph.autonomy.models import ActionSafetyRule
from life_graph.autonomy.safety.service import SafetyRuleService
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

AMBIENT_PROJECT_ID = "ambient"
AMBIENT_AUTONOMY_LEVEL = 1  # L1: Safe Auto — safe actions auto-execute, rest need approval

# Infra rules for the shell-command actions the ops persona proposes. action_name values
# are distinct from SafetyRuleService.seed_defaults' app-level defaults (e.g. "delete_data")
# so both sets coexist without colliding on the tenant-unique action_name constraint.
INFRA_SAFETY_RULES: list[dict] = [
    # Safe — read-only inspection commands.
    {
        "action_name": "docker_ps",
        "action_pattern": "docker_ps",
        "risk_level": "safe",
        "trust_threshold": 0.3,
        "priority": 10,
        "description": "List docker containers",
    },
    {
        "action_name": "disk_check",
        "action_pattern": "disk*",
        "risk_level": "safe",
        "trust_threshold": 0.3,
        "priority": 10,
        "description": "Check disk usage",
    },
    {
        "action_name": "memory_check",
        "action_pattern": "memory*",
        "risk_level": "safe",
        "trust_threshold": 0.3,
        "priority": 10,
        "description": "Check memory usage",
    },
    {
        "action_name": "git_status_check",
        "action_pattern": "git_status",
        "risk_level": "safe",
        "trust_threshold": 0.3,
        "priority": 10,
        "description": "Check git status",
    },
    # Moderate — service restarts.
    {
        "action_name": "restart_service",
        "action_pattern": "restart_*",
        "risk_level": "moderate",
        "trust_threshold": 0.6,
        "priority": 50,
        "description": "Restart a service",
    },
    {
        "action_name": "docker_restart",
        "action_pattern": "docker restart *",
        "risk_level": "moderate",
        "trust_threshold": 0.6,
        "priority": 50,
        "description": "Restart a docker container",
    },
    # Dangerous — destructive/irreversible; guardrail-gated regardless of trust score.
    {
        "action_name": "rm_command",
        "action_pattern": "rm *",
        "risk_level": "dangerous",
        "trust_threshold": 0.9,
        "priority": 95,
        "is_guardrail": True,
        "is_reversible": False,
        "description": "Remove files (irreversible)",
    },
    {
        "action_name": "delete_infra",
        "action_pattern": "delete_*",
        "risk_level": "dangerous",
        "trust_threshold": 0.9,
        "priority": 95,
        "is_guardrail": True,
        "is_reversible": False,
        "description": "Delete an infrastructure resource (irreversible)",
    },
    {
        "action_name": "drop_command",
        "action_pattern": "drop *",
        "risk_level": "dangerous",
        "trust_threshold": 0.9,
        "priority": 95,
        "is_guardrail": True,
        "is_reversible": False,
        "description": "Drop a database object (irreversible)",
    },
    {
        "action_name": "migration_downgrade",
        "action_pattern": "*migrat*downgrade*",
        "risk_level": "dangerous",
        "trust_threshold": 0.9,
        "priority": 95,
        "is_guardrail": True,
        "is_reversible": False,
        "description": "Database migration downgrade (irreversible schema change)",
    },
]

# Code-action rules for the cody ambient-action persona's agent_task proposals
# (see kernel.ambient.AMBIENT_ACTION, kernel.propose_contract.AGENT_TASK_PROPOSE_CONTRACT).
# Task 2's router forces every agent_task proposal to queue for approval regardless of
# risk_level — these rules only set the risk badge the approvals UI displays.
CODY_SAFETY_RULES: list[dict] = [
    {
        "action_name": "cody_fix",
        "action_pattern": "cody_fix",
        "risk_level": "moderate",
        "trust_threshold": 0.6,
        "priority": 50,
        "description": "Propose a fix for a failing test or known issue",
    },
    {
        "action_name": "cody_refactor",
        "action_pattern": "cody_refactor",
        "risk_level": "moderate",
        "trust_threshold": 0.6,
        "priority": 50,
        "description": "Propose a code refactor",
    },
]


async def seed_ambient_autonomy(tenant_id: str) -> None:
    """Seed default + infra safety rules and set the ambient project to L1. Idempotent.

    Mirrors ``seed_ambient_jobs``: safe to call on every startup.
    ``SafetyRuleService.seed_defaults`` already skips action_names that exist; the infra
    rules loop here does the same diff-by-name check. ``set_manual`` is a plain write —
    re-running it just reaffirms L1, it never errors on a second call.
    """
    async with async_session() as session:
        safety_svc = SafetyRuleService(session)
        await safety_svc.seed_defaults(tenant_id)

        existing = (
            (
                await session.execute(
                    select(ActionSafetyRule.action_name).where(
                        ActionSafetyRule.tenant_id == tenant_id
                    )
                )
            )
            .scalars()
            .all()
        )
        existing_names = set(existing)

        created = 0
        for rule in INFRA_SAFETY_RULES + CODY_SAFETY_RULES:
            if rule["action_name"] in existing_names:
                continue
            await safety_svc.create_rule(tenant_id=tenant_id, created_by="system", **rule)
            created += 1

        await session.commit()

    logger.info(
        "Seeded %d infra/cody safety rules for tenant=%s (ambient)", created, tenant_id
    )

    level_svc = AutonomyLevelService(session_factory=async_session)
    await level_svc.set_manual(
        tenant_id,
        AMBIENT_PROJECT_ID,
        AMBIENT_AUTONOMY_LEVEL,
        "Ambient ops autonomy default (Sub-project B startup seeding)",
        "system",
    )

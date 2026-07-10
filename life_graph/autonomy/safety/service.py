"""Safety rule service — CRUD and seeding for action_safety_rules."""

from __future__ import annotations

import logging

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.autonomy.models import ActionSafetyRule
from life_graph.models.db import _utcnow

logger = logging.getLogger(__name__)


class SafetyRuleService:
    """Manages safety rule lifecycle — create, read, update, delete, seed."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_rule(
        self,
        tenant_id: str,
        action_name: str,
        action_pattern: str,
        risk_level: str = "dangerous",
        created_by: str = "system",
        **kwargs,
    ) -> ActionSafetyRule:
        """Create a new safety rule."""
        rule = ActionSafetyRule(
            tenant_id=tenant_id,
            action_name=action_name,
            action_pattern=action_pattern,
            risk_level=risk_level,
            created_by=created_by,
            **kwargs,
        )
        self._session.add(rule)
        await self._session.flush()
        logger.info(
            "Created safety rule: tenant=%s, action=%s, risk=%s",
            tenant_id, action_name, risk_level,
        )
        return rule

    async def get_rule(
        self, tenant_id: str, rule_id: str
    ) -> ActionSafetyRule | None:
        """Get a single safety rule by ID."""
        stmt = select(ActionSafetyRule).where(
            ActionSafetyRule.id == rule_id,
            ActionSafetyRule.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_rules(
        self,
        tenant_id: str,
        enabled_only: bool = True,
        category: str | None = None,
        risk_level: str | None = None,
    ) -> list[ActionSafetyRule]:
        """List safety rules with optional filters."""
        stmt = select(ActionSafetyRule).where(
            ActionSafetyRule.tenant_id == tenant_id
        )

        if enabled_only:
            stmt = stmt.where(ActionSafetyRule.enabled.is_(True))
        if category:
            stmt = stmt.where(ActionSafetyRule.category == category)
        if risk_level:
            stmt = stmt.where(ActionSafetyRule.risk_level == risk_level)

        stmt = stmt.order_by(ActionSafetyRule.priority.asc())
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update_rule(
        self, tenant_id: str, rule_id: str, **updates
    ) -> ActionSafetyRule | None:
        """Update a safety rule's fields."""
        rule = await self.get_rule(tenant_id, rule_id)
        if rule is None:
            return None

        for key, value in updates.items():
            if hasattr(rule, key):
                setattr(rule, key, value)

        rule.updated_at = _utcnow()
        await self._session.flush()
        logger.info("Updated safety rule: %s", rule_id)
        return rule

    async def delete_rule(self, tenant_id: str, rule_id: str) -> bool:
        """Delete a safety rule. Returns True if deleted."""
        stmt = delete(ActionSafetyRule).where(
            ActionSafetyRule.id == rule_id,
            ActionSafetyRule.tenant_id == tenant_id,
        )
        result = await self._session.execute(stmt)
        deleted = result.rowcount > 0
        if deleted:
            logger.info("Deleted safety rule: %s", rule_id)
        return deleted

    async def import_rules(
        self,
        tenant_id: str,
        rules: list[dict],
        created_by: str = "import",
    ) -> list[ActionSafetyRule]:
        """Bulk import rules from a list of dicts."""
        created = []
        for rule_data in rules:
            action_name = rule_data.pop("action_name")
            action_pattern = rule_data.pop("action_pattern")
            risk_level = rule_data.pop("risk_level", "dangerous")

            rule = await self.create_rule(
                tenant_id=tenant_id,
                action_name=action_name,
                action_pattern=action_pattern,
                risk_level=risk_level,
                created_by=created_by,
                **rule_data,
            )
            created.append(rule)

        logger.info("Imported %d safety rules for tenant=%s", len(created), tenant_id)
        return created

    async def seed_defaults(
        self, tenant_id: str, created_by: str = "system"
    ) -> list[ActionSafetyRule]:
        """Seed default safety rules for a tenant.

        Skips rules that already exist (by action_name) to avoid duplicates.
        """
        defaults = [
            {
                "action_name": "rotate_logs",
                "action_pattern": "rotate_logs",
                "risk_level": "safe",
                "trust_threshold": 0.3,
                "priority": 10,
                "description": "Rotate log files",
            },
            {
                "action_name": "clear_cache",
                "action_pattern": "clear_cache*",
                "risk_level": "safe",
                "trust_threshold": 0.3,
                "priority": 10,
                "description": "Clear application caches",
            },
            {
                "action_name": "fix_lint",
                "action_pattern": "fix_lint*",
                "risk_level": "safe",
                "trust_threshold": 0.3,
                "priority": 10,
                "description": "Auto-fix lint issues",
            },
            {
                "action_name": "run_tests",
                "action_pattern": "run_tests*",
                "risk_level": "safe",
                "trust_threshold": 0.3,
                "priority": 10,
                "description": "Run test suites",
            },
            {
                "action_name": "deploy_staging",
                "action_pattern": "deploy_staging*",
                "risk_level": "moderate",
                "trust_threshold": 0.5,
                "priority": 50,
                "description": "Deploy to staging environment",
            },
            {
                "action_name": "update_deps",
                "action_pattern": "update_dep*",
                "risk_level": "moderate",
                "trust_threshold": 0.6,
                "priority": 50,
                "description": "Update project dependencies",
            },
            {
                "action_name": "deploy_production",
                "action_pattern": "deploy_prod*",
                "risk_level": "dangerous",
                "trust_threshold": 0.8,
                "priority": 90,
                "is_guardrail": True,
                "description": "Deploy to production environment",
            },
            {
                "action_name": "delete_data",
                "action_pattern": "delete_*",
                "risk_level": "dangerous",
                "trust_threshold": 0.9,
                "priority": 95,
                "is_guardrail": True,
                "is_reversible": False,
                "description": "Delete data (destructive, irreversible)",
            },
        ]

        # Check existing rules to avoid duplicates
        existing_stmt = select(ActionSafetyRule.action_name).where(
            ActionSafetyRule.tenant_id == tenant_id
        )
        result = await self._session.execute(existing_stmt)
        existing_names = {row[0] for row in result.all()}

        created = []
        for rule_data in defaults:
            if rule_data["action_name"] in existing_names:
                logger.debug(
                    "Skipping existing rule: %s", rule_data["action_name"]
                )
                continue

            rule = await self.create_rule(
                tenant_id=tenant_id,
                created_by=created_by,
                **rule_data,
            )
            created.append(rule)

        logger.info(
            "Seeded %d default safety rules for tenant=%s (skipped %d existing)",
            len(created),
            tenant_id,
            len(defaults) - len(created),
        )
        return created

"""Ambient advisory roles: the personas that run on a schedule and only report."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

AMBIENT_ADVISORY: frozenset[str] = frozenset({"scout", "admin", "tutor"})

# Roles that run on a schedule in PROPOSE mode: read-only investigation, then
# a JSON array of proposed actions for the user to approve — never executed
# automatically. See AMBIENT_ACTION_READONLY_TOOLS below for the enforced toolset.
AMBIENT_ACTION: frozenset[str] = frozenset({"ops"})

# Tools a scheduled AMBIENT_ACTION run is restricted to — read-only by construction,
# so an unattended ops sweep can investigate but never mutate anything.
AMBIENT_ACTION_READONLY_TOOLS: list[str] = [
    "inspect_system",
    "git_status",
    "git_log",
    "git_diff",
    "memory_search",
    "get_current_datetime",
]

# Cron 01:00 UTC — before settings.brief_hour_utc (=2) so findings make the brief.
AMBIENT_JOBS: list[dict[str, Any]] = [
    {
        "name": "scout-daily",
        "cron_expression": "0 1 * * *",
        "agent_name": "scout",
        "description": "Ambient research on your watch-list; surfaces new findings.",
        "input": {"topics": []},
        "active": True,
    },
    {
        "name": "admin-daily",
        "cron_expression": "0 1 * * *",
        "agent_name": "admin",
        "description": "Surfaces work/life admin items needing attention.",
        "input": {},
        "active": True,
    },
    {
        "name": "tutor-daily",
        "cron_expression": "0 1 * * *",
        "agent_name": "tutor",
        "description": "Proactive learning nudges (opt-in).",
        "input": {},
        "active": False,
    },
    {
        "name": "ops-ambient",
        "cron_expression": "0 1 * * *",
        "agent_name": "ops",
        "description": "Ambient infra sweep: proposes maintenance actions for your approval.",
        "input": {},
        "active": False,  # opt-in — acts on real infra
    },
]


async def seed_ambient_jobs(scheduler: Any, tenant_id: str) -> int:
    """Create the ambient ScheduledJobs for a tenant if absent. Idempotent.

    Mirrors PersonaService.seed_builtins: diff by name, create only the missing.
    tutor-daily is created then deactivated (create has no is_active field).
    Returns the number of jobs created.
    """
    existing, _ = await scheduler.list_all(tenant_id, include_inactive=True)
    existing_names = {j["name"] for j in existing}
    created = 0
    for defn in AMBIENT_JOBS:
        if defn["name"] in existing_names:
            continue
        try:
            row = await scheduler.create(
                tenant_id,
                {
                    "name": defn["name"],
                    "cron_expression": defn["cron_expression"],
                    "agent_name": defn["agent_name"],
                    "description": defn["description"],
                    "input": defn["input"],
                },
            )
            created += 1
            if not defn["active"] and row and row.get("id"):
                await scheduler.update(tenant_id, row["id"], {"is_active": False})
        except ValueError:
            # Raced with another seeder for the same name — fine.
            logger.debug("Ambient job %s already exists for %s", defn["name"], tenant_id)
    return created

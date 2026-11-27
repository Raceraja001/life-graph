"""The gate in front of every automatic action of Phase 4b.

docs/specs/agent-drivers.md, "Phase 4b". Starting a held task once its
dependencies finished, and handing PR feedback back to a task, happen without
anyone pressing a button. Before each of them this asks, in order:

1. the **kill switch** -- a paused tenant gets nothing automatic;
2. the **subscription share** (risk D4, only with agent accounts on) -- an
   account at or above ``driver_accounts_subscription_max_share`` of its plan
   window, or every account cooling down, waits;
3. the **Governor** -- the monthly dollar cap, as an unattended spend (skipped
   when the run will be billed to a subscription account, which reports $0).

Any refusal is a reason string; the caller waits and records it. A check that
cannot be made refuses (CHARTER invariant 5, fail closed) -- except the
Governor, whose own documented behaviour on a storage error is to fail open.
"""

from __future__ import annotations

import logging
from typing import Any

from life_graph.autonomy.kill_switch import autonomy_stopped
from life_graph.core.budget import BudgetCategory
from life_graph.drivers import accounts_hook
from life_graph.drivers.registry import driver_registry
from life_graph.services.governor import governor

logger = logging.getLogger(__name__)


async def blockers(
    tenant_id: str, *, driver: str | None = None, account_id: Any = None
) -> list[str]:
    """Why an automatic action for *tenant_id* must wait now ([] = it may go)."""
    try:
        if await autonomy_stopped(tenant_id):
            return ["Autonomy is paused (kill switch)."]
    except Exception:
        logger.warning("Kill-switch check failed for %s", tenant_id, exc_info=True)
        return ["The kill switch could not be read."]

    reasons: list[str] = []
    subscription = False
    if driver:
        try:
            preview = await accounts_hook.preview(
                driver, tenant_id, unattended=True, account_id=account_id
            )
        except Exception:
            logger.warning("Account preview failed for %s", driver, exc_info=True)
            preview = {"state": "error"}
        state = (preview or {}).get("state")
        if state == "over_budget":
            reason = ((preview or {}).get("budget") or {}).get("reason") or "over its share"
            reasons.append(f"Every {driver} account is over the subscription share ({reason}).")
        elif state == "cooling":
            reasons.append(f"Every {driver} account is cooling down after a rate limit.")
        elif state == "error":
            reasons.append(f"The {driver} account pool could not be read.")
        elif state == "selected" and (preview or {}).get("kind") == "subscription":
            subscription = True
    if reasons:
        return reasons

    if not subscription:
        instance = driver_registry.get(driver) if driver else None
        try:
            estimate = float(instance.cost_per_task()) if instance is not None else 0.0
        except Exception:  # best-effort: an unknown price is estimated as $0 (cap still applies)
            estimate = 0.0
        decision = await governor.authorize(
            tenant_id, BudgetCategory.DRIVER, estimated_usd=estimate, interactive=False
        )
        if not decision.allowed:
            reasons.append(f"Budget: {decision.reason}.")
    return reasons

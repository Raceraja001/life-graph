"""Budget policy — the Governor's single source of truth.

Every autonomous spender (drivers, research, failure-mining, advisors, watchers)
must be authorized before it spends. This module holds the pure decision logic;
``services/governor.py`` wraps it with persistence and wiring.

Posture (decided in the Track 2 brainstorm):
    **Throttle autonomous spend when the budget runs low; never block the user's
    own interactive requests.**

No DB, no I/O, no imports from the rest of the app.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class BudgetPriority(str, Enum):
    """How aggressively a category is throttled as the budget fills up."""

    HIGH = "high"  # acts on the user's live tasks/decisions — throttled last
    LOW = "low"    # background maintenance — throttled first


class BudgetCategory(str, Enum):
    """A spender bucket. New spenders add a member here + a priority below."""

    DRIVER = "driver"
    ADVISOR = "advisor"
    RESEARCH = "research"
    FAILURE_MINING = "failure_mining"
    WATCHER = "watcher"


# Priority per category — the only place throttle order is defined.
_CATEGORY_PRIORITY: dict[BudgetCategory, BudgetPriority] = {
    BudgetCategory.DRIVER: BudgetPriority.HIGH,
    BudgetCategory.ADVISOR: BudgetPriority.HIGH,
    BudgetCategory.RESEARCH: BudgetPriority.LOW,
    BudgetCategory.FAILURE_MINING: BudgetPriority.LOW,
    BudgetCategory.WATCHER: BudgetPriority.LOW,
}

DEFAULT_SOFT_THRESHOLD = 0.8


def priority_for(category: BudgetCategory) -> BudgetPriority:
    """Return a category's throttle priority (defaults to LOW if unmapped)."""
    return _CATEGORY_PRIORITY.get(category, BudgetPriority.LOW)


@dataclass(frozen=True)
class BudgetDecision:
    """The Governor's verdict on a single spend request.

    Attributes:
        allowed: Whether the spend may proceed.
        throttled: True when the request is at/over a threshold — either denied,
            or allowed-but-flagged (interactive over cap). Signals "budget pressure".
        reason: Human-readable explanation (for logs, brief, alerts).
        spent_usd: Month-to-date spend at decision time.
        cap_usd: The monthly cap in effect.
        remaining_usd: ``max(0, cap - spent)``.
    """

    allowed: bool
    throttled: bool
    reason: str
    spent_usd: float
    cap_usd: float
    remaining_usd: float


def decide(
    spent_usd: float,
    cap_usd: float,
    priority: BudgetPriority,
    *,
    interactive: bool,
    soft_threshold: float = DEFAULT_SOFT_THRESHOLD,
) -> BudgetDecision:
    """Decide whether a spend is authorized — the entire posture, purely.

    Args:
        spent_usd: Month-to-date spend for the tenant.
        cap_usd: Monthly budget cap. Non-positive disables gating (always allow).
        priority: The spending category's throttle priority.
        interactive: True for user-initiated requests — never blocked.
        soft_threshold: Fraction of the cap at which low-priority autonomous
            spend starts being throttled (default 0.8).

    Returns:
        A :class:`BudgetDecision`.
    """
    remaining = max(0.0, cap_usd - spent_usd)

    def _decision(allowed: bool, throttled: bool, reason: str) -> BudgetDecision:
        return BudgetDecision(
            allowed=allowed,
            throttled=throttled,
            reason=reason,
            spent_usd=spent_usd,
            cap_usd=cap_usd,
            remaining_usd=remaining,
        )

    # A non-positive cap means "no budget enforcement configured" — never freeze
    # the system on a misconfiguration.
    if cap_usd <= 0:
        return _decision(True, False, "budget gating disabled (cap <= 0)")

    over_cap = spent_usd >= cap_usd
    over_soft = spent_usd >= soft_threshold * cap_usd

    # Interactive (user-initiated) requests are always allowed — flagged as
    # throttled only to signal pressure when already over cap.
    if interactive:
        if over_cap:
            return _decision(True, True, "interactive allowed over cap (budget exhausted)")
        return _decision(True, False, "interactive allowed")

    # Autonomous spend.
    if over_cap:
        return _decision(False, True, "monthly budget exhausted; autonomous spend denied")
    if over_soft:
        if priority is BudgetPriority.HIGH:
            return _decision(True, False, "over soft threshold; high-priority allowed")
        return _decision(
            False, True,
            "over soft threshold; low-priority autonomous throttled",
        )
    return _decision(True, False, "within budget")

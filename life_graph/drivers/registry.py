"""Driver Registry — manages available agent drivers.

Provides a singleton registry for registering, discovering, and
querying agent drivers by name or task type capability.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from life_graph.drivers.base import AgentDriver

logger = logging.getLogger(__name__)

# How a driver's runs are paid for, cheapest first: on this machine, on a
# flat subscription (marginal cost $0, but limited), or metered per call.
BILLING_ORDER: tuple[str, ...] = ("local", "subscription", "api")


def billing_of(driver: object) -> str:
    """A driver's ``billing`` attribute; one without it counts as ``api``."""
    value = getattr(driver, "billing", None)
    return value if value in BILLING_ORDER else "api"


def selection_key(driver: AgentDriver) -> tuple[float, int]:
    """Cheapest-capable order: estimated cost, then local < subscription < api.

    A subscription CLI reports $0 per task like a local model; at equal cost
    the local driver still comes first.
    """
    return (driver.cost_per_task(), BILLING_ORDER.index(billing_of(driver)))


class DriverRegistry:
    """Registry of available agent drivers.

    Drivers register themselves at startup. The dispatch pipeline
    queries the registry to find suitable drivers for a given task.
    """

    def __init__(self) -> None:
        self._drivers: dict[str, AgentDriver] = {}

    def register(self, driver: AgentDriver) -> None:
        """Register a driver instance.

        Args:
            driver: An object implementing the AgentDriver protocol.
        """
        self._drivers[driver.name] = driver
        logger.info("Registered driver: %s", driver.name)

    def get(self, name: str) -> AgentDriver | None:
        """Get a driver by name.

        Args:
            name: The driver's unique name.

        Returns:
            The driver instance, or None if not found.
        """
        return self._drivers.get(name)

    def list_all(self) -> list[AgentDriver]:
        """Return all registered drivers."""
        return list(self._drivers.values())

    def available_for_task(self, task_type: str) -> list[AgentDriver]:
        """Return drivers that can handle a given task type.

        Args:
            task_type: The type of task to find drivers for.

        Returns:
            List of drivers whose capabilities include the task type.
        """
        return [d for d in self._drivers.values() if task_type in d.capabilities()]


# ── Global singleton ─────────────────────────────────────────
driver_registry = DriverRegistry()

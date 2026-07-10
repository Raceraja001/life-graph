"""Driver Registry — manages available agent drivers.

Provides a singleton registry for registering, discovering, and
querying agent drivers by name or task type capability.
"""

from __future__ import annotations

import logging

from life_graph.drivers.base import AgentDriver

logger = logging.getLogger(__name__)


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

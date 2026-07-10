"""Agent Drivers — the interface for renting external agents.

Drivers wrap external agent systems (Claude Code, Codex, local orchestrator)
as interchangeable workers that receive context packets and return results.
"""

from life_graph.drivers.base import AgentDriver, ContextPacket, DriverResult
from life_graph.drivers.registry import DriverRegistry, driver_registry

__all__ = [
    "AgentDriver",
    "ContextPacket",
    "DriverResult",
    "DriverRegistry",
    "driver_registry",
]

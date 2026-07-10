"""Agent Driver Protocol — the interface for renting external agents.

Drivers wrap external agent systems (Claude Code, Codex, local orchestrator)
as interchangeable workers that receive context packets and return results.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class ContextPacket:
    """Everything an agent needs to do its job.

    Assembled by the context builder from the Life Graph substrate:
    project info, procedures, preferences, memories, and calibration data.

    Attributes:
        task_id: Unique identifier for the task being dispatched.
        tenant_id: Tenant scope for multi-tenant isolation.
        task_type: Category of work (code, research, analysis, etc.).
        instruction: Natural language description of what to do.
        project_context: Project metadata, file tree, dependencies.
        procedures: Relevant learned procedures for this task type.
        preferences: User preferences that should influence behavior.
        memories: Relevant memories from semantic search.
        calibration_profile: Bias info for the agent (over/under-confidence).
        max_tokens: Token budget for the entire context packet.
        private: If True, strip memories/preferences for external drivers.
    """

    task_id: uuid.UUID
    tenant_id: str
    task_type: str
    instruction: str
    project_context: dict = field(default_factory=dict)
    procedures: list[dict] = field(default_factory=list)
    preferences: list[dict] = field(default_factory=list)
    memories: list[dict] = field(default_factory=list)
    calibration_profile: dict = field(default_factory=dict)
    max_tokens: int = 6000
    private: bool = False


@dataclass
class DriverResult:
    """What comes back from a driver dispatch.

    Attributes:
        success: Whether the task completed successfully.
        output: Text output from the agent.
        artifacts: List of file artifacts [{path, content, action}].
        cost_usd: Estimated cost in USD for this dispatch.
        duration_ms: Wall-clock time in milliseconds.
        error: Error message if the task failed.
        metadata: Driver-specific metadata.
    """

    success: bool
    output: str = ""
    artifacts: list[dict] = field(default_factory=list)
    cost_usd: float = 0.0
    duration_ms: int = 0
    error: str | None = None
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class AgentDriver(Protocol):
    """Protocol for agent drivers.

    Any class implementing this protocol can be registered in the
    DriverRegistry and used by the dispatch pipeline to execute tasks.
    """

    name: str

    async def available(self) -> bool:
        """Check if this driver is ready to accept tasks."""
        ...

    async def dispatch(
        self, packet: ContextPacket, workdir: Path, timeout: int = 300
    ) -> DriverResult:
        """Send a task to this driver and wait for result.

        Args:
            packet: The context packet with all task information.
            workdir: Working directory for file operations.
            timeout: Maximum seconds to wait for completion.

        Returns:
            DriverResult with the outcome of the dispatch.
        """
        ...

    def capabilities(self) -> list[str]:
        """Return list of task types this driver can handle."""
        ...

    def cost_per_task(self) -> float:
        """Estimated cost in USD per task."""
        ...

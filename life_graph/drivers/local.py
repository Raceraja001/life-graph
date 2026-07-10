"""Local Driver — wraps the existing AgentOrchestrator.

Used for cheap, private, small tasks that don't need external agents.
The orchestrator's ``run()`` method is a streaming async generator that
takes messages and system_prompt, so we format the context packet as a
conversation and collect the streamed output.
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from life_graph.drivers.base import AgentDriver, ContextPacket, DriverResult

logger = logging.getLogger(__name__)


class LocalDriver:
    """Wraps the existing local AgentOrchestrator as an AgentDriver.

    Always available, zero cost. For private tasks that should never
    leave the local system.
    """

    name = "local"

    async def available(self) -> bool:
        """Local driver is always available."""
        return True

    async def dispatch(
        self, packet: ContextPacket, workdir: Path, timeout: int = 300
    ) -> DriverResult:
        """Dispatch a task to the local AgentOrchestrator.

        Formats the context packet as a conversation message, runs the
        orchestrator's streaming loop, and collects the output.

        Args:
            packet: The context packet with task information.
            workdir: Working directory (unused by local orchestrator).
            timeout: Maximum seconds (applied at orchestrator level).

        Returns:
            DriverResult with the collected output.
        """
        start = time.monotonic()
        try:
            from life_graph.agents.orchestrator import AgentOrchestrator

            orchestrator = AgentOrchestrator()

            # Build a system prompt from the context packet
            system_parts = ["You are an AI agent executing a task."]
            if packet.project_context:
                system_parts.append(
                    f"Project context: {json.dumps(packet.project_context, default=str)}"
                )
            if packet.preferences:
                system_parts.append(
                    f"User preferences: {json.dumps(packet.preferences, default=str)}"
                )
            if packet.procedures:
                system_parts.append(
                    f"Relevant procedures: {json.dumps(packet.procedures, default=str)}"
                )

            system_prompt = "\n\n".join(system_parts)
            messages = [{"role": "user", "content": packet.instruction}]

            # Collect streamed output (the orchestrator yields SSE events)
            output_parts: list[str] = []
            async for event_str in orchestrator.run(
                messages=messages,
                system_prompt=system_prompt,
            ):
                # Parse SSE data lines to extract content tokens
                if event_str.startswith("data: "):
                    try:
                        data = json.loads(event_str[6:].strip())
                        if data.get("type") == "token" and data.get("content"):
                            output_parts.append(data["content"])
                    except (json.JSONDecodeError, KeyError):
                        pass

            duration = int((time.monotonic() - start) * 1000)
            return DriverResult(
                success=True,
                output="".join(output_parts),
                cost_usd=0.0,
                duration_ms=duration,
            )

        except Exception as e:
            duration = int((time.monotonic() - start) * 1000)
            logger.error("Local driver failed: %s", e, exc_info=True)
            return DriverResult(
                success=False,
                error=str(e),
                duration_ms=duration,
            )

    def capabilities(self) -> list[str]:
        """Return task types the local driver can handle."""
        return ["code", "research", "analysis", "general"]

    def cost_per_task(self) -> float:
        """Local execution is free (uses local LLM or configured model)."""
        return 0.0

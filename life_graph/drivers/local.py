"""Local Driver — wraps the existing AgentOrchestrator.

Used for cheap, private tasks that should never leave the machine: the model
is the dispatching persona's (typically an Ollama model such as
``ollama_chat/qwen3-coder:30b``). The orchestrator's ``run()`` is a streaming
async generator, so the context packet is formatted as a conversation and the
streamed output collected.

For coding work three things the chat loop never needed are enforced here:

* **Confinement to the worktree.** Host file tools are scoped to ``workdir``
  for the whole run (:func:`life_graph.tools._guards.confine_to`): the agent
  can reach the task's worktree and nothing else — not the rest of the
  projects folder, not the live checkout the worktree was cut from.
* **Room to work.** A code change is read → search → edit → re-read; the chat
  loop's 8 tool rounds end mid-edit. The driver allows
  :attr:`MAX_AGENT_ITERATIONS` and a longer :attr:`dispatch_timeout`, which
  the dispatcher reads.
* **Honest failure.** The run is failed when the orchestrator reports an
  error or the time budget runs out, instead of reporting success with
  whatever partial text streamed.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from life_graph.drivers.base import ContextPacket, DriverResult

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class LocalDriver:
    """Wraps the existing local AgentOrchestrator as an AgentDriver.

    Always available, zero cost. For private tasks that should never
    leave the local system.
    """

    name = "local"
    # A local 30B model on a consumer GPU is slow per round; the dispatcher
    # uses this instead of its 300s default.
    dispatch_timeout = 1200
    MAX_AGENT_ITERATIONS = 40

    async def available(self) -> bool:
        """Local driver is always available."""
        return True

    async def dispatch(
        self, packet: ContextPacket, workdir: Path, timeout: int = 300
    ) -> DriverResult:
        """Dispatch a task to the local AgentOrchestrator.

        When the packet carries persona scoping (``persona_system_prompt`` /
        ``allowed_tools``, set by ``TaskDispatcher.dispatch_task`` for a
        persona-pinned dispatch), the persona's own prompt is used as the base
        system prompt and the orchestrator is handed ONLY that persona's tools
        — mirroring ``kernel/process_manager.py::_run_agent``. Without it the
        orchestrator resolves the entire tool registry, which includes the
        host shell (``run_command``); that is safety-load-bearing for
        unattended dispatches, do not remove.

        Args:
            packet: The context packet with task information.
            workdir: The task's working directory; host file tools are
                confined to it for the duration of the run.
            timeout: Maximum seconds for the whole agent run.

        Returns:
            DriverResult with the collected output.
        """
        start = time.monotonic()
        try:
            from life_graph.agents.orchestrator import AgentOrchestrator
            from life_graph.tools._guards import confine_to

            orchestrator = (
                AgentOrchestrator(model=packet.persona_model)
                if packet.persona_model
                else AgentOrchestrator()
            )
            orchestrator.MAX_ITERATIONS = self.MAX_AGENT_ITERATIONS

            # Build a system prompt from the context packet
            system_parts = [
                packet.persona_system_prompt or "You are an AI agent executing a task.",
                f"The project is checked out at {workdir}; file tools are confined to it. "
                "Paths for code_read / code_edit / code_search / code_list may be "
                "relative to that root. Read the relevant code before editing, make "
                "edits with code_edit, and re-read what you changed.",
            ]
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

            # Persona tool scoping. None => no persona resolved, keep the
            # historical full-registry behavior (the orchestrator resolves the
            # registry itself when tools is None). A list — even empty — is an
            # explicit allowlist and is passed through verbatim.
            run_kwargs: dict = {}
            if packet.allowed_tools is not None:
                from life_graph.tools.registry import registry as tool_registry

                allowed_set = set(packet.allowed_tools)
                run_kwargs["tools"] = [
                    t for t in tool_registry.get_tools() if t["function"]["name"] in allowed_set
                ]

            output_parts: list[str] = []
            tool_calls = 0
            errors: list[str] = []

            async def collect() -> None:
                nonlocal tool_calls
                async for event_str in orchestrator.run(
                    messages=messages,
                    system_prompt=system_prompt,
                    **run_kwargs,
                ):
                    if not event_str.startswith("data: "):
                        continue
                    try:
                        data = json.loads(event_str[6:].strip())
                    except json.JSONDecodeError:
                        continue
                    kind = data.get("type")
                    if kind == "token" and data.get("content"):
                        output_parts.append(data["content"])
                    elif kind == "tool_call":
                        tool_calls += 1
                    elif kind == "error":
                        errors.append(str(data.get("message") or data.get("error") or data))

            with confine_to(workdir):
                try:
                    await asyncio.wait_for(collect(), timeout=timeout)
                except TimeoutError:
                    errors.append(f"local driver timed out after {timeout}s")

            duration = int((time.monotonic() - start) * 1000)
            return DriverResult(
                success=not errors,
                output="".join(output_parts),
                cost_usd=0.0,
                duration_ms=duration,
                error="; ".join(errors)[:2000] if errors else None,
                metadata={
                    "model": getattr(orchestrator, "model", packet.persona_model),
                    "tool_calls": tool_calls,
                    "workdir": str(workdir),
                },
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

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
  error (``error`` or ``partial_error``), runs out of rounds, stops for being
  stuck in a loop, makes no tool calls at all on a coding task, or the time
  budget runs out, instead of reporting success with whatever partial text
  streamed. ``metadata.stop_reason`` says which.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import TYPE_CHECKING

from life_graph.agents.stuck import is_error_result
from life_graph.drivers import self_check
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.steps import StepCollector

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

# Tools that change files; a coding run where none of them succeeded changed nothing.
EDIT_TOOLS = frozenset({"code_edit", "file_write"})

# How many times a coding run that ends its turn without a landed edit is sent
# back to work. A live run (gpt-oss:20b, 2026-10-16) read the file, then
# replied with nothing after eight calls; it never got to the edit.
MAX_NO_EDIT_NUDGES = 2
NO_EDIT_NUDGE = (
    "You have not changed any file yet, and this task needs a change. Make the "
    "edit now with code_edit, then re-read the file to check it. "
    "If the change is impossible, say exactly why."
)
NO_PLAN_NUDGE = (
    "You have not written the plan yet. Stop exploring and write it now: start "
    "with the line '## Spec', then **Requirements:**, **Design:** and **Tasks:** "
    "exactly as the task describes."
)


class LocalDriver:
    """Wraps the existing local AgentOrchestrator as an AgentDriver.

    Always available, zero cost. For private tasks that should never
    leave the local system.
    """

    name = "local"
    # A local 30B model on a consumer GPU is slow per round; the dispatcher
    # uses this instead of its 300s default.
    dispatch_timeout = 1200
    # Was 40, partly because the context could not hold more rounds; the
    # condenser (agents/condenser.py) now keeps a long run inside the window.
    MAX_AGENT_ITERATIONS = 60

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
            steps = StepCollector()
            tool_calls = 0
            condensed = 0
            good_edits = failed_edits = 0
            errors: list[str] = []
            stop_reason = "completed"
            nudges = 0
            may_edit = packet.task_type in ("code", "code_change") and (
                packet.allowed_tools is None or bool(EDIT_TOOLS & set(packet.allowed_tools))
            )

            self_checks = 0

            async def keep_going() -> str | None:
                nonlocal nudges, self_checks
                if packet.task_type == "plan":
                    # Plan runs deliver text, not edits: one ended after twenty
                    # reads with an empty reply (task f5d3c67a, 2026-10-18).
                    if "## Spec" in "".join(output_parts) or nudges >= MAX_NO_EDIT_NUDGES:
                        return None
                    nudges += 1
                    return NO_PLAN_NUDGE
                if not may_edit:
                    return None
                if not good_edits:
                    if nudges >= MAX_NO_EDIT_NUDGES:
                        return None
                    nudges += 1
                    return NO_EDIT_NUDGE
                # Edited: run the tests it added or changed (drivers/self_check.py).
                if self_checks >= self_check.MAX_SELF_CHECKS:
                    return None
                feedback = await self_check.check(
                    workdir, packet.project_context or {}, packet.instruction
                )
                if feedback:
                    self_checks += 1
                return feedback

            async def collect() -> None:
                nonlocal tool_calls, condensed, stop_reason, good_edits, failed_edits
                async for event_str in orchestrator.run(
                    messages=messages,
                    system_prompt=system_prompt,
                    keep_going=keep_going,
                    **run_kwargs,
                ):
                    if not event_str.startswith("data: "):
                        continue
                    try:
                        data = json.loads(event_str[6:].strip())
                    except json.JSONDecodeError:
                        continue
                    steps.add(data)
                    kind = data.get("type")
                    if kind == "token" and data.get("content"):
                        output_parts.append(data["content"])
                    elif kind == "tool_call":
                        tool_calls += 1
                    elif kind == "tool_result" and data.get("name") in EDIT_TOOLS:
                        if is_error_result(str(data.get("result") or "")):
                            failed_edits += 1
                        else:
                            good_edits += 1
                    elif kind == "condensed":
                        condensed += 1
                    elif kind in ("error", "partial_error"):
                        # The orchestrator reports failures as partial_error
                        # ("All models are currently unavailable"); counting
                        # only "error" returned those runs as successes.
                        errors.append(str(data.get("message") or data.get("error") or data))
                        stop_reason = "error"
                    elif kind == "done" and data.get("stop_reason") in ("max_iterations", "stuck"):
                        stop_reason = data["stop_reason"]
                        errors.append(
                            "ran out of tool rounds"
                            if stop_reason == "max_iterations"
                            else str(data.get("warning") or "stuck in a loop")
                        )

            from life_graph.tools.run_tests import project_settings

            with confine_to(workdir), project_settings(packet.project_context or {}):
                try:
                    await asyncio.wait_for(collect(), timeout=timeout)
                except TimeoutError:
                    errors.append(f"local driver timed out after {timeout}s")
                    stop_reason = "timeout"

            output = "".join(output_parts)
            if (
                not errors
                and tool_calls == 0
                and packet.task_type in ("code", "code_change")
                and packet.allowed_tools != []
            ):
                # A coding task that never touched a tool changed nothing. A
                # live trial (qwen3-coder:30b, 2026-10-14) answered in prose
                # and was reported as a success; verifiers caught it, but the
                # driver's own record should not say it worked.
                stop_reason = "no_action"
                errors.append(
                    "the model wrote tool calls as text instead of making them"
                    if _looks_like_text_tool_calls(output)
                    else "the model made no tool calls, so nothing was changed"
                )
            elif (
                not errors
                and good_edits == 0
                and packet.task_type in ("code", "code_change")
                and (packet.allowed_tools is None or EDIT_TOOLS & set(packet.allowed_tools))
            ):
                # Tools were used but nothing was written: every edit was
                # refused ("`old` not found"), or none was tried. A live run
                # (qwen3:14b, 2026-10-15) ended like that and was reported as
                # a success.
                stop_reason = "no_change"
                errors.append(
                    f"all {failed_edits} edit(s) failed, so nothing was changed"
                    if failed_edits
                    else "the model never edited a file, so nothing was changed"
                )

            duration = int((time.monotonic() - start) * 1000)
            return DriverResult(
                success=not errors,
                output=output,
                cost_usd=0.0,
                duration_ms=duration,
                error="; ".join(errors)[:2000] if errors else None,
                metadata={
                    "model": getattr(orchestrator, "model", packet.persona_model),
                    "tool_calls": tool_calls,
                    "condensed": condensed,
                    "nudges": nudges,
                    "self_checks": self_checks,
                    "stop_reason": stop_reason,
                    "steps": steps.finish(),
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
        return ["code", "code_change", "research", "analysis", "general"]

    def cost_per_task(self) -> float:
        """Local execution is free (uses local LLM or configured model)."""
        return 0.0


_TEXT_TOOL_CALL_MARKERS = ("<tool_call>", "<function=", '"name": "code_', "```tool")


def _looks_like_text_tool_calls(output: str) -> bool:
    """A model whose chat template failed writes the call into its reply."""
    return any(marker in output for marker in _TEXT_TOOL_CALL_MARKERS)

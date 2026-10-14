"""Agent orchestrator with LLM tool-calling loop.

Manages the iterative cycle of LLM generation → tool execution → result
injection → continued generation, streaming all intermediate steps as
Server-Sent Events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING, Any

from life_graph.config import Settings
from life_graph.connectors.locality import audience_for_model
from life_graph.services.claude_cli_reply import run_claude_cli
from life_graph.services.resilient_llm import ResilientLLMExhaustedError
from life_graph.tools.registry import registry

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

logger = logging.getLogger(__name__)


class AgentOrchestrator:
    """Orchestrates LLM interactions with tool use in a loop.

    Sends messages to the LLM, detects tool calls, executes them via
    the global tool registry, feeds results back, and continues until
    the LLM produces a final text response or the iteration limit is
    reached.

    Attributes:
        MAX_ITERATIONS: Maximum tool-calling loop iterations to prevent
            infinite loops.
    """

    # Was 5. Observed in production: a single browsing task easily spends
    # one iteration per candidate source (navigate -> read), and a slow or
    # dead site can burn a full 60s bridged-tool timeout for zero progress
    # (see BRIDGED_TOOL_TIMEOUT_SECONDS in mcp_bridge.py) — 5 left no room
    # to recover from one bad navigation plus try 2-3 more sources.
    MAX_ITERATIONS: int = 8
    MAX_RETRIES: int = 2
    RETRY_DELAY_BASE: float = 1.0  # exponential backoff base in seconds
    FALLBACK_MODEL: str = "gemini/gemini-3.5-flash-lite"  # overridden in __init__ from config

    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        settings = Settings()
        self.model = model or settings.agent_llm_model
        self.temperature = (
            temperature if temperature is not None else settings.agent_llm_temperature
        )
        self.max_tokens = max_tokens or settings.agent_llm_max_tokens
        self.FALLBACK_MODEL = settings.agent_fallback_model
        # docs/specs/agent-condenser.md: keep long runs inside the context
        # window and notice loops.
        self.condense = settings.agent_condenser_enabled
        self.detect_stuck = settings.agent_stuck_detection
        self.context_tokens = settings.context_tokens_for(self.model)

    async def run(
        self,
        messages: list[dict[str, Any]],
        system_prompt: str | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncGenerator[str, None]:
        """Run the agent loop, streaming SSE events.

        Event types yielded:
            - ``token``      — incremental content token
            - ``tool_call``  — a tool is being invoked
            - ``tool_result``— tool execution result
            - ``done``       — generation complete
            - ``error``      — an error occurred

        Args:
            messages: Conversation history.
            system_prompt: Optional system prompt to prepend.
            tools: Tool definitions (defaults to global registry).

        Yields:
            SSE-formatted event strings.
        """
        # Resolve tools from registry if not provided.
        resolved_tools = tools if tools is not None else registry.get_tools()
        has_tools = bool(resolved_tools)
        # The exact set of tool names advertised to the LLM this run —
        # also the enforcement boundary at execute time (see below), so a
        # persona's allowed_tools filtering can't be bypassed by a model
        # emitting a tool_call for a tool it was never shown.
        allowed_tool_names = {t["function"]["name"] for t in resolved_tools}

        # Build working message list.
        working_messages: list[dict[str, Any]] = []
        if system_prompt:
            working_messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )
        working_messages.extend(messages)

        if self.model == "claude-cli":
            try:
                prompt = "\n".join(
                    f"{msg['role']}: {msg.get('content') or ''}" for msg in working_messages
                )
                # claude-cli replies have zero tool access by design (see
                # docs/superpowers/specs/2026-08-08-claude-cli-model-routing-design.md).
                # A persona's system prompt may itself instruct tool use or
                # delegation (e.g. jarvis's whole prompt is delegation
                # instructions) — make the no-tools constraint explicit so
                # the model doesn't hallucinate having delegated or run a
                # tool that never executed.
                prompt += (
                    "\n\n(No tools are available this turn. Answer directly; do not "
                    "claim to have delegated to another persona or run any tool.)"
                )
                result = await run_claude_cli(prompt)
            except Exception as exc:
                # Any unexpected failure here (message flattening or the CLI
                # call itself) falls into the same graceful shape as a
                # run_claude_cli() failure below, matching the existing
                # ResilientLLMExhaustedError failure shape exactly
                # (orchestrator.py:297-304) — "partial_error" with a
                # "message" key, always followed by a terminal "done".
                yield _sse({"type": "partial_error", "message": str(exc), "retryable": True})
                yield _sse({"type": "done", "model": self.model, "tokens": 0})
                return

            if not result.success:
                # Matches the existing ResilientLLMExhaustedError failure shape
                # exactly (orchestrator.py:297-304) — "partial_error" with a
                # "message" key, always followed by a terminal "done".
                yield _sse({"type": "partial_error", "message": result.error, "retryable": True})
                yield _sse({"type": "done", "model": self.model, "tokens": 0})
                return

            yield _sse({"type": "token", "content": result.text})
            yield _sse(
                {
                    "type": "usage",
                    "completion_tokens": len(result.text.split()),
                    "total_tokens": len(result.text.split()),
                }
            )
            yield _sse({"type": "done", "model": self.model, "tokens": len(result.text.split())})
            return

        logger.info(
            "Agent run started: model=%s, tools=%d, messages=%d",
            self.model,
            len(resolved_tools) if resolved_tools else 0,
            len(working_messages),
        )

        total_tokens = 0
        self._retry_count = 0
        from life_graph.agents import condenser
        from life_graph.agents.stuck import StuckDetector, nudge_text

        detector = StuckDetector() if self.detect_stuck else None
        budget = condenser.budget_for(self.context_tokens, self.max_tokens)

        for iteration in range(self.MAX_ITERATIONS):
            logger.debug("Agent iteration %d/%d", iteration + 1, self.MAX_ITERATIONS)

            try:
                from life_graph.api.dependencies import get_resilient_llm

                if self.condense and iteration > 0:
                    # Fit the conversation into the window BEFORE sending it:
                    # an over-long prompt loses its beginning (the system
                    # prompt and the task) inside the model server.
                    result_c = await condenser.condense(
                        working_messages,
                        budget=budget,
                        summarise=condenser.summariser_for(
                            get_resilient_llm().acompletion, self.model
                        ),
                        model=self.model,
                    )
                    if result_c.layer is not None:
                        messages_before = len(working_messages)
                        working_messages[:] = result_c.messages
                        yield _sse(
                            {
                                "type": "condensed",
                                "layer": result_c.layer,
                                "before_tokens": result_c.before_tokens,
                                "after_tokens": result_c.after_tokens,
                                "budget": budget,
                                "messages_before": messages_before,
                                "messages_after": len(working_messages),
                            }
                        )

                # Build completion kwargs.
                completion_kwargs: dict[str, Any] = {
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": True,
                }
                if has_tools:
                    completion_kwargs["tools"] = resolved_tools
                    completion_kwargs["tool_choice"] = "auto"

                response = await get_resilient_llm().acompletion(
                    messages=working_messages,
                    model=self.model,
                    **completion_kwargs,
                )

                # Accumulate content and tool calls from the stream.
                content_parts: list[str] = []
                tool_calls_acc: dict[int, dict[str, Any]] = {}
                # Ollama (through LiteLLM) sends each parallel tool call whole,
                # every one at index 0. Accumulating by index alone glued them
                # into one call with arguments like '{"days": 1}{}', and the
                # next request was rejected for it, failing the whole run. A
                # delta that starts a new call at a used index gets its own slot.
                remap: dict[int, int] = {}

                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if delta is None:
                        continue

                    # Stream content tokens.
                    if delta.content:
                        content_parts.append(delta.content)
                        total_tokens += 1
                        yield _sse(
                            {
                                "type": "token",
                                "content": delta.content,
                            }
                        )

                    # Accumulate tool calls across chunks.
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            raw_idx = tc.index if tc.index is not None else 0
                            idx = remap.get(raw_idx, raw_idx)
                            slot = tool_calls_acc.get(idx)
                            starts_new = bool(
                                tc.function
                                and tc.function.name
                                and slot is not None
                                and slot["name"]
                            ) or bool(
                                tc.id and slot is not None and slot["id"] and tc.id != slot["id"]
                            )
                            if starts_new:
                                idx = max(tool_calls_acc) + 1
                                remap[raw_idx] = idx
                            if idx not in tool_calls_acc:
                                tool_calls_acc[idx] = {
                                    "id": tc.id or "",
                                    "name": "",
                                    "arguments": "",
                                }
                            if tc.id:
                                tool_calls_acc[idx]["id"] = tc.id
                            if tc.function:
                                if tc.function.name:
                                    tool_calls_acc[idx]["name"] = tc.function.name
                                if tc.function.arguments:
                                    tool_calls_acc[idx]["arguments"] += tc.function.arguments

                # If no tool calls, we're done.
                if not tool_calls_acc:
                    logger.info(
                        "Agent completed: iterations=%d, tokens=%d",
                        iteration + 1,
                        total_tokens,
                    )
                    # Emit usage data for frontend token display
                    yield _sse(
                        {
                            "type": "usage",
                            "completion_tokens": total_tokens,
                            "total_tokens": total_tokens,
                        }
                    )
                    yield _sse(
                        {
                            "type": "done",
                            "model": self.model,
                            "tokens": total_tokens,
                            "stop_reason": "completed",
                        }
                    )
                    return

                # Build assistant message with tool calls for context.
                assistant_tool_calls = []
                for idx in sorted(tool_calls_acc.keys()):
                    tc_data = tool_calls_acc[idx]
                    assistant_tool_calls.append(
                        {
                            # Blank ids (Ollama) would make every tool result
                            # answer the same call.
                            "id": tc_data["id"] or f"call_{iteration}_{idx}",
                            "type": "function",
                            "function": {
                                "name": tc_data["name"],
                                "arguments": _valid_json_args(tc_data["arguments"]),
                            },
                        }
                    )

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(content_parts) or None,
                    "tool_calls": assistant_tool_calls,
                }
                working_messages.append(assistant_msg)

                # Execute each tool call.
                stuck = None
                for tc_info in assistant_tool_calls:
                    tool_name = tc_info["function"]["name"]
                    raw_args = tc_info["function"]["arguments"]

                    try:
                        tool_args = json.loads(raw_args) if raw_args else {}
                    except json.JSONDecodeError:
                        tool_args = {}
                        logger.warning(
                            "Failed to parse tool args for %s: %s",
                            tool_name,
                            raw_args[:100],
                        )

                    # Signal tool execution start.
                    yield _sse(
                        {
                            "type": "tool_call",
                            "name": tool_name,
                            "arguments": tool_args,
                            "status": "running",
                        }
                    )

                    # Execute the tool — but only if it's within the set
                    # advertised for this run. This is the actual
                    # enforcement point: filtering what's shown to the
                    # model (above) is advisory only until execution is
                    # gated the same way, otherwise a persona could still
                    # invoke a disallowed tool (e.g. delegate_to_persona)
                    # if the model emits it, such as via prompt injection.
                    if tool_name not in allowed_tool_names:
                        logger.warning(
                            "Blocked disallowed tool call: %s is not in"
                            " the allowed tool set for this run",
                            tool_name,
                        )
                        result = json.dumps(
                            {
                                "error": (f"tool '{tool_name}' is not permitted for this persona"),
                            }
                        )
                    else:
                        try:
                            # Tools that hold personal data (connectors) read
                            # this to decide what the model may see: local
                            # only if this model and every fallback it could
                            # fail over to mid-run are on this machine.
                            with audience_for_model(self.model):
                                result = await registry.execute(tool_name, tool_args)
                        except KeyError:
                            result = json.dumps(
                                {
                                    "error": f"Unknown tool: {tool_name}",
                                }
                            )

                    # Signal tool execution result.
                    yield _sse(
                        {
                            "type": "tool_result",
                            "name": tool_name,
                            "result": result,
                        }
                    )

                    # Append tool result for next LLM iteration. One huge
                    # result (a log, a whole file) keeps its head and tail
                    # rather than filling the window by itself.
                    working_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc_info["id"],
                            "content": condenser.cap_result(str(result)),
                        }
                    )
                    if detector is not None and stuck is None:
                        stuck = detector.record(tool_name, tool_args, str(result))

                logger.debug(
                    "Tool calls executed: %s",
                    [tc["function"]["name"] for tc in assistant_tool_calls],
                )
                self._retry_count = 0  # reset on success

                if stuck is not None:
                    # Acted on only after every result of this turn is in, so
                    # no message lands between a tool call and its result.
                    if detector.detections == 1:
                        yield _sse(
                            {
                                "type": "stuck",
                                "pattern": stuck.pattern,
                                "tool": stuck.tool,
                                "action": "nudged",
                            }
                        )
                        working_messages.append({"role": "user", "content": nudge_text(stuck)})
                    else:
                        logger.warning(
                            "Agent stuck again (%s on %s); stopping", stuck.pattern, stuck.tool
                        )
                        yield _sse(
                            {
                                "type": "stuck",
                                "pattern": stuck.pattern,
                                "tool": stuck.tool,
                                "action": "stopped",
                            }
                        )
                        yield _sse(
                            {
                                "type": "usage",
                                "completion_tokens": total_tokens,
                                "total_tokens": total_tokens,
                            }
                        )
                        yield _sse(
                            {
                                "type": "done",
                                "model": self.model,
                                "tokens": total_tokens,
                                "stop_reason": "stuck",
                                "warning": f"Stopped: stuck in a loop ({stuck.pattern}).",
                            }
                        )
                        return

            except ResilientLLMExhaustedError as exc:
                # ResilientLLM already tried the caller's model plus the whole
                # configured fallback chain (with cooldown-aware skipping) and
                # every attempt failed — nothing left for the orchestrator to
                # retry or switch to. Surface one clear terminal error.
                logger.error("All models exhausted for agent run: %s", exc)
                yield _sse(
                    {
                        "type": "partial_error",
                        "message": "All models are currently unavailable. Please try again shortly.",
                        "retryable": True,
                    }
                )
                yield _sse(
                    {
                        "type": "done",
                        "model": self.model,
                        "tokens": total_tokens,
                        "stop_reason": "error",
                    }
                )
                return

            except Exception as exc:
                # Unknown errors — retry once, then fail
                retry_count = self._retry_count
                self._retry_count = retry_count + 1

                if retry_count < 1:  # single retry for unknown errors
                    logger.warning(
                        "Unexpected error, retrying once: %s",
                        exc,
                    )
                    yield _sse(
                        {
                            "type": "status",
                            "message": "Recovering from error...",
                        }
                    )
                    await asyncio.sleep(1.0)
                    continue

                logger.exception("Unrecoverable agent error: %s", exc)
                yield _sse(
                    {
                        "type": "partial_error",
                        "message": f"Internal error: {type(exc).__name__}",
                        "retryable": True,
                    }
                )
                yield _sse(
                    {
                        "type": "done",
                        "model": self.model,
                        "tokens": total_tokens,
                        "stop_reason": "error",
                    }
                )
                return

        # Max iterations reached.
        logger.warning("Agent hit max iterations (%d)", self.MAX_ITERATIONS)
        yield _sse(
            {
                "type": "usage",
                "completion_tokens": total_tokens,
                "total_tokens": total_tokens,
            }
        )
        yield _sse(
            {
                "type": "done",
                "model": self.model,
                "tokens": total_tokens,
                "warning": "Max tool-calling iterations reached.",
                "stop_reason": "max_iterations",
            }
        )


# ── SSE Helpers ─────────────────────────────────────────────


def _sse(data: dict[str, Any]) -> str:
    """Format a dictionary as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _valid_json_args(raw: str) -> str:
    """Tool-call arguments that a model server will accept back.

    The arguments are echoed to the model in the next request, and Ollama
    rejects the whole request when they are not a JSON object. Keep the first
    complete object of a garbled string ('{"a": 1}{}' → '{"a": 1}'), or send
    an empty object; the tool itself already ran with what could be parsed.
    """
    if not raw:
        return "{}"
    try:
        value = json.loads(raw)
        return raw if isinstance(value, dict) else "{}"
    except json.JSONDecodeError:
        pass
    try:
        value, _end = json.JSONDecoder().raw_decode(raw.lstrip())
    except json.JSONDecodeError:
        return "{}"
    return json.dumps(value) if isinstance(value, dict) else "{}"

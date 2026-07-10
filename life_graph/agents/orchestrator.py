"""Agent orchestrator with LLM tool-calling loop.

Manages the iterative cycle of LLM generation → tool execution → result
injection → continued generation, streaming all intermediate steps as
Server-Sent Events.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from typing import Any

import litellm

from life_graph.tools.registry import registry
from life_graph.config import Settings

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

    MAX_ITERATIONS: int = 5
    MAX_RETRIES: int = 2
    RETRY_DELAY_BASE: float = 1.0  # exponential backoff base in seconds
    FALLBACK_MODEL: str = "gemini/gemini-2.0-flash"  # overridden in __init__ from config

    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        settings = Settings()
        self.model = model or settings.agent_llm_model
        self.temperature = (
            temperature if temperature is not None
            else settings.agent_llm_temperature
        )
        self.max_tokens = max_tokens or settings.agent_llm_max_tokens
        self.FALLBACK_MODEL = settings.agent_fallback_model

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

        # Build working message list.
        working_messages: list[dict[str, Any]] = []
        if system_prompt:
            working_messages.append({
                "role": "system",
                "content": system_prompt,
            })
        working_messages.extend(messages)

        logger.info(
            "Agent run started: model=%s, tools=%d, messages=%d",
            self.model,
            len(resolved_tools) if resolved_tools else 0,
            len(working_messages),
        )

        total_tokens = 0
        self._retry_count = 0

        for iteration in range(self.MAX_ITERATIONS):
            logger.debug("Agent iteration %d/%d", iteration + 1, self.MAX_ITERATIONS)

            try:
                # Build completion kwargs.
                completion_kwargs: dict[str, Any] = {
                    "model": self.model,
                    "messages": working_messages,
                    "temperature": self.temperature,
                    "max_tokens": self.max_tokens,
                    "stream": True,
                }
                if has_tools:
                    completion_kwargs["tools"] = resolved_tools
                    completion_kwargs["tool_choice"] = "auto"

                response = await litellm.acompletion(
                    **completion_kwargs
                )

                # Accumulate content and tool calls from the stream.
                content_parts: list[str] = []
                tool_calls_acc: dict[int, dict[str, Any]] = {}

                async for chunk in response:
                    delta = (
                        chunk.choices[0].delta
                        if chunk.choices
                        else None
                    )
                    if delta is None:
                        continue

                    # Stream content tokens.
                    if delta.content:
                        content_parts.append(delta.content)
                        total_tokens += 1
                        yield _sse({
                            "type": "token",
                            "content": delta.content,
                        })

                    # Accumulate tool calls across chunks.
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index if tc.index is not None else 0
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
                                    tool_calls_acc[idx]["name"] = (
                                        tc.function.name
                                    )
                                if tc.function.arguments:
                                    tool_calls_acc[idx]["arguments"] += (
                                        tc.function.arguments
                                    )

                # If no tool calls, we're done.
                if not tool_calls_acc:
                    logger.info(
                        "Agent completed: iterations=%d, tokens=%d",
                        iteration + 1,
                        total_tokens,
                    )
                    # Emit usage data for frontend token display
                    yield _sse({
                        "type": "usage",
                        "completion_tokens": total_tokens,
                        "total_tokens": total_tokens,
                    })
                    yield _sse({
                        "type": "done",
                        "model": self.model,
                        "tokens": total_tokens,
                    })
                    return

                # Build assistant message with tool calls for context.
                assistant_tool_calls = []
                for idx in sorted(tool_calls_acc.keys()):
                    tc_data = tool_calls_acc[idx]
                    assistant_tool_calls.append({
                        "id": tc_data["id"],
                        "type": "function",
                        "function": {
                            "name": tc_data["name"],
                            "arguments": tc_data["arguments"],
                        },
                    })

                assistant_msg: dict[str, Any] = {
                    "role": "assistant",
                    "content": "".join(content_parts) or None,
                    "tool_calls": assistant_tool_calls,
                }
                working_messages.append(assistant_msg)

                # Execute each tool call.
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
                    yield _sse({
                        "type": "tool_call",
                        "name": tool_name,
                        "arguments": tool_args,
                        "status": "running",
                    })

                    # Execute the tool.
                    try:
                        result = await registry.execute(
                            tool_name, tool_args
                        )
                    except KeyError:
                        result = json.dumps({
                            "error": f"Unknown tool: {tool_name}",
                        })

                    # Signal tool execution result.
                    yield _sse({
                        "type": "tool_result",
                        "name": tool_name,
                        "result": result,
                    })

                    # Append tool result for next LLM iteration.
                    working_messages.append({
                        "role": "tool",
                        "tool_call_id": tc_info["id"],
                        "content": result,
                    })

                logger.debug(
                    "Tool calls executed: %s",
                    [tc["function"]["name"] for tc in assistant_tool_calls],
                )
                self._retry_count = 0  # reset on success

            except (litellm.RateLimitError, litellm.Timeout) as exc:
                # Retryable errors — wait and retry, then fallback model
                retry_count = self._retry_count
                self._retry_count = retry_count + 1

                if retry_count < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY_BASE * (2 ** retry_count)
                    logger.warning(
                        "Retryable error (attempt %d/%d): %s. Retrying in %.1fs",
                        retry_count + 1, self.MAX_RETRIES, exc, delay,
                    )
                    yield _sse({
                        "type": "status",
                        "message": f"Retrying... (attempt {retry_count + 2})",
                    })
                    await asyncio.sleep(delay)
                    continue  # retry the iteration

                # Max retries exhausted — try fallback model
                if self.model != self.FALLBACK_MODEL:
                    logger.warning(
                        "Switching to fallback model %s after %d retries",
                        self.FALLBACK_MODEL, self.MAX_RETRIES,
                    )
                    self.model = self.FALLBACK_MODEL
                    self._retry_count = 0  # reset for fallback
                    yield _sse({
                        "type": "status",
                        "content": "Switching to a faster model due to temporary issues",
                    })
                    yield _sse({
                        "type": "status",
                        "message": "Switching to fallback model...",
                    })
                    continue  # retry with fallback

                # Fallback also failed
                logger.error("All retries and fallback exhausted: %s", exc)
                yield _sse({
                    "type": "partial_error",
                    "message": "Service temporarily unavailable. Please try again.",
                    "retryable": True,
                })
                yield _sse({"type": "done", "model": self.model, "tokens": total_tokens})
                return

            except litellm.AuthenticationError as exc:
                # Non-retryable — bad API key, no point retrying
                logger.error("Auth error during agent run: %s", exc)
                yield _sse_error("Authentication error. Check your API key.")
                return

            except Exception as exc:
                # Unknown errors — retry once, then fail
                retry_count = self._retry_count
                self._retry_count = retry_count + 1

                if retry_count < 1:  # single retry for unknown errors
                    logger.warning(
                        "Unexpected error, retrying once: %s", exc,
                    )
                    yield _sse({
                        "type": "status",
                        "message": "Recovering from error...",
                    })
                    await asyncio.sleep(1.0)
                    continue

                logger.exception("Unrecoverable agent error: %s", exc)
                yield _sse({
                    "type": "partial_error",
                    "message": f"Internal error: {type(exc).__name__}",
                    "retryable": True,
                })
                yield _sse({"type": "done", "model": self.model, "tokens": total_tokens})
                return

        # Max iterations reached.
        logger.warning(
            "Agent hit max iterations (%d)", self.MAX_ITERATIONS
        )
        yield _sse({
            "type": "usage",
            "completion_tokens": total_tokens,
            "total_tokens": total_tokens,
        })
        yield _sse({
            "type": "done",
            "model": self.model,
            "tokens": total_tokens,
            "warning": "Max tool-calling iterations reached.",
        })


# ── SSE Helpers ─────────────────────────────────────────────


def _sse(data: dict[str, Any]) -> str:
    """Format a dictionary as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


def _sse_error(message: str) -> str:
    """Format an error as an SSE data line."""
    return _sse({"type": "error", "message": message})

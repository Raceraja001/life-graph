"""Tool registry for agent function calling.

Provides a centralised registry where tools can be registered via decorator
or direct API call, discovered in OpenAI function-calling format, and
executed by the agent orchestrator.
"""

from __future__ import annotations

import asyncio
import difflib
import inspect
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

MAX_TOOL_RESULT_CHARS = 4000
TOOL_TIMEOUT_SECONDS = 15

# A post-execution hook receives one observation dict and returns nothing.
PostExecHook = Callable[[dict[str, Any]], Awaitable[None]]


def _closest_param(arg: str, free: list[str]) -> str | None:
    """The parameter a misnamed argument most likely meant, if it is clear.

    Same words in another order (``line_start`` for ``start_line``) or a near
    spelling (``contents`` for ``content``)."""
    words = sorted(arg.lower().split("_"))
    same = [p for p in free if sorted(p.lower().split("_")) == words]
    if len(same) == 1:
        return same[0]
    close = difflib.get_close_matches(arg, free, n=2, cutoff=0.8)
    return close[0] if len(close) == 1 else None


def _signature_text(sig: inspect.Signature) -> str:
    out = []
    for name, p in sig.parameters.items():
        if p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD):
            continue
        out.append(f"{name} (required)" if p.default is p.empty else f"{name}={p.default!r}")
    return ", ".join(out)


def fit_args(
    name: str, handler: Callable[..., Any], args: dict[str, Any]
) -> tuple[dict[str, Any], str | None]:
    """Fit a model's arguments to the handler before calling it.

    Local models guess parameter names. A live run (gpt-oss:20b, 2026-10-16)
    sent ``code_read(line_start=…)`` and then left out ``path``; each got a
    bare ``TypeError`` and it never got to the edit. A clear near-miss is
    renamed; anything else returns an error that lists the real parameters.
    """
    try:
        sig = inspect.signature(handler)
    except (TypeError, ValueError):
        return args, None
    params = sig.parameters
    if any(p.kind is p.VAR_KEYWORD for p in params.values()):
        return args, None
    fixed = {k: v for k, v in args.items() if k in params}
    unknown = [k for k in args if k not in params]
    for k in unknown:
        free = [
            p
            for p, spec in params.items()
            if p not in fixed and spec.kind in (spec.POSITIONAL_OR_KEYWORD, spec.KEYWORD_ONLY)
        ]
        target = _closest_param(k, free)
        if target is None:
            return args, f"{name} has no parameter '{k}'. Parameters: {_signature_text(sig)}"
        fixed[target] = args[k]
    try:
        sig.bind(**fixed)
    except TypeError as exc:
        return args, f"Bad arguments for {name}: {exc}. Parameters: {_signature_text(sig)}"
    return fixed, None


@dataclass
class ToolEntry:
    """A registered tool with its metadata and handler."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Callable[..., Any]
    timeout_seconds: int = TOOL_TIMEOUT_SECONDS


class ToolRegistry:
    """Central registry for agent-callable tools.

    Tools can be registered imperatively via :meth:`register` or
    declaratively via the :func:`tool` decorator.
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolEntry] = {}
        self._post_exec_hooks: list[PostExecHook] = []

    # ── Post-execution hooks ──────────────────────────────────

    def add_post_exec_hook(self, hook: PostExecHook) -> None:
        """Register an async hook fired after every tool execution.

        Each hook receives an observation dict
        ``{tool, args_summary, exit_status, duration_ms}``. Hooks are
        best-effort — an exception in one never affects the tool result
        or other hooks.
        """
        self._post_exec_hooks.append(hook)

    def clear_post_exec_hooks(self) -> None:
        """Remove all registered post-execution hooks (mainly for tests)."""
        self._post_exec_hooks.clear()

    async def _fire_post_exec(
        self,
        name: str,
        args: dict[str, Any],
        exit_status: str,
        start: float,
    ) -> None:
        """Build the observation and dispatch it to all hooks."""
        if not self._post_exec_hooks:
            return
        from life_graph.core.redaction import summarize_args

        observation = {
            "tool": name,
            "args_summary": summarize_args(args),
            "exit_status": exit_status,
            "duration_ms": int((time.monotonic() - start) * 1000),
        }
        for hook in self._post_exec_hooks:
            try:
                await hook(observation)
            except Exception:
                logger.debug("post-exec hook failed for tool %s", name, exc_info=True)

    def register(
        self,
        name: str,
        description: str,
        parameters_schema: dict[str, Any],
        handler: Callable[..., Any],
        timeout_seconds: int | None = None,
    ) -> None:
        """Register a tool with the given metadata and handler.

        Args:
            name: Unique tool name.
            description: Human-readable description for the LLM.
            parameters_schema: JSON Schema for the tool's parameters.
            handler: Sync or async callable that implements the tool.
            timeout_seconds: Per-tool override for the execution timeout.
                Defaults to TOOL_TIMEOUT_SECONDS when omitted — every
                existing caller that doesn't pass this keeps today's
                behavior unchanged. Exists for callers whose tools are
                inherently slower than a typical local one (e.g. the MCP
                bridge's browser-automation tools, doing real network I/O
                against real websites).
        """
        if name in self._tools:
            logger.warning("Overwriting existing tool: %s", name)

        self._tools[name] = ToolEntry(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            handler=handler,
            timeout_seconds=timeout_seconds
            if timeout_seconds is not None
            else TOOL_TIMEOUT_SECONDS,
        )
        logger.info("Registered tool: %s", name)

    def get_tools(self) -> list[dict[str, Any]]:
        """Return all tools in OpenAI function-calling format.

        Returns:
            List of tool definitions compatible with the OpenAI API.
        """
        return [
            {
                "type": "function",
                "function": {
                    "name": entry.name,
                    "description": entry.description,
                    "parameters": entry.parameters_schema,
                },
            }
            for entry in self._tools.values()
        ]

    async def execute(self, name: str, args: dict[str, Any]) -> str:
        """Execute a registered tool by name.

        Handles both sync and async handlers transparently.

        Args:
            name: The tool name to execute.
            args: Keyword arguments to pass to the handler.

        Returns:
            Tool result as a string (JSON-serialised if not already str).

        Raises:
            KeyError: If the tool name is not registered.
        """
        if name not in self._tools:
            error_msg = f"Unknown tool: '{name}'"
            logger.error(error_msg)
            raise KeyError(error_msg)

        entry = self._tools[name]
        logger.info("Executing tool: %s with args: %s", name, args)

        args, arg_error = fit_args(name, entry.handler, args)
        if arg_error:
            return json.dumps({"error": arg_error})

        start = time.monotonic()
        try:
            if asyncio.iscoroutinefunction(entry.handler):
                result = await asyncio.wait_for(
                    entry.handler(**args),
                    timeout=entry.timeout_seconds,
                )
            else:
                result = entry.handler(**args)
        except TimeoutError:
            logger.warning("Tool '%s' timed out after %ds", name, entry.timeout_seconds)
            await self._fire_post_exec(name, args, "timeout", start)
            return json.dumps({"error": f"Tool '{name}' timed out after {entry.timeout_seconds}s"})
        except Exception as exc:
            logger.exception("Tool '%s' failed: %s", name, exc)
            await self._fire_post_exec(name, args, "error", start)
            return json.dumps(
                {
                    "error": f"Tool execution failed: {exc}",
                }
            )

        await self._fire_post_exec(name, args, "ok", start)

        output = result if isinstance(result, str) else json.dumps(result)

        # Truncate oversized results (JSON-aware)
        if len(output) > MAX_TOOL_RESULT_CHARS:
            logger.warning(
                "Tool '%s' result truncated: %d -> %d chars",
                name,
                len(output),
                MAX_TOOL_RESULT_CHARS,
            )
            # Try to truncate JSON arrays intelligently
            try:
                parsed = json.loads(output)
                if isinstance(parsed, dict):
                    # Find the first list value and truncate it
                    for key, val in parsed.items():
                        if isinstance(val, list) and len(val) > 3:
                            parsed[key] = val[:5]
                            parsed["_truncated"] = True
                            parsed["_total_items"] = len(val)
                            output = json.dumps(parsed)
                            break
                    else:
                        # No list found — fall back to char truncation
                        output = output[:MAX_TOOL_RESULT_CHARS] + '..."}'
                elif isinstance(parsed, list) and len(parsed) > 3:
                    truncated_list = parsed[:5]
                    output = json.dumps(
                        {"results": truncated_list, "_truncated": True, "_total_items": len(parsed)}
                    )
                else:
                    output = output[:MAX_TOOL_RESULT_CHARS] + '..."}'
            except (json.JSONDecodeError, TypeError):
                output = output[:MAX_TOOL_RESULT_CHARS] + "\n\n[... truncated]"

        return output

    @property
    def tool_names(self) -> list[str]:
        """Return the list of registered tool names."""
        return list(self._tools.keys())


# ── Global registry instance ───────────────────────────────

registry = ToolRegistry()


# ── Decorator ───────────────────────────────────────────────


def tool(
    name: str,
    description: str,
    parameters_schema: dict[str, Any],
) -> Callable[..., Any]:
    """Decorator to register a function as an agent tool.

    Example::

        @tool(
            name="my_tool",
            description="Does something useful",
            parameters_schema={"type": "object", "properties": {...}},
        )
        async def my_tool(arg1: str) -> str:
            return "result"

    Args:
        name: Unique tool name.
        description: Human-readable description for the LLM.
        parameters_schema: JSON Schema for the tool's parameters.

    Returns:
        The original function, now registered in the global registry.
    """

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        registry.register(name, description, parameters_schema, func)
        return func

    return decorator

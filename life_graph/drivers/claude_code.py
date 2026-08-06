"""Claude Code headless driver — wrap, don't rebuild (strategic-decision.md).

Invokes the Claude Code CLI in headless mode (``claude -p "<packet>"
--output-format json``) with ``cwd`` set to the project path — or an
isolated git worktree when the project context asks for isolation —
and normalizes the JSON result to a :class:`DriverResult`.

Graceful degradation: when the ``claude`` binary is not installed on
this host, :meth:`available` returns False and the dispatcher skips
this driver (same pattern as the era-4 advisor's missing API keys).
"""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import time
from typing import TYPE_CHECKING

from life_graph.config import settings
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.context import render_memory_block
from life_graph.drivers.workdir import remove_worktree, resolve_workdir

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_COST_PER_TASK_USD = 0.10  # frontier cost class; actual cost read from CLI output

_ALLOWED_TOOLS_FLAG = "--allowedTools"

# life_graph tool registry name → Claude Code CLI's own tool name. The CLI
# has a different, coarser tool vocabulary (no separate git_status/git_diff/
# etc. — all shell-adjacent operations go through "Bash"). Names with no
# sensible CLI equivalent (delegate_to_persona, calculator,
# get_current_datetime, inspect_system) are simply absent — an allowed_tools
# list containing only those maps to an empty CLI allowlist, fail-closed,
# matching LocalDriver's behavior for an unmapped/unregistered name.
_TOOL_NAME_TO_CLI: dict[str, str] = {
    "run_command": "Bash",
    "git_status": "Bash",
    "git_log": "Bash",
    "git_diff": "Bash",
    "git_branch": "Bash",
    "file_read": "Read",
    "file_write": "Write",
    "web_search": "WebSearch",
    "browse_web": "WebFetch",
    "browser_agent": "WebFetch",
}


def _allowed_cli_tools(allowed_tools: list[str] | None) -> list[str] | None:
    """Translate life_graph tool names into Claude Code CLI tool names.

    Returns ``None`` when ``allowed_tools`` is ``None`` (no persona scoping —
    the CLI keeps its own default permissions, matching the "no scoping"
    contract ``ContextPacket.allowed_tools`` already documents). A present
    list — even if every name is unmapped — produces a (possibly empty)
    explicit CLI allowlist, fail-closed.
    """
    if allowed_tools is None:
        return None
    mapped = {
        _TOOL_NAME_TO_CLI[name] for name in allowed_tools if name in _TOOL_NAME_TO_CLI
    }
    return sorted(mapped)


class ClaudeCodeDriver:
    """Wraps Claude Code headless mode as an AgentDriver."""

    name = "claude_code"
    max_concurrency = 2

    def __init__(self, binary: str | None = None) -> None:
        self._binary = binary or getattr(
            settings, "driver_claude_code_bin", "claude"
        )

    # ── Protocol ──────────────────────────────────────────────

    async def available(self) -> bool:
        """Ready when the Claude Code binary is on PATH."""
        found = shutil.which(self._binary) is not None
        if not found:
            logger.debug("claude_code unavailable: %r not on PATH", self._binary)
        return found

    async def dispatch(
        self, packet: ContextPacket, workdir: Path, timeout: int = 300
    ) -> DriverResult:
        """Run Claude Code headless on the packet and normalize the result.

        The working directory is the project path from the packet when it
        exists (or an isolated git worktree of it when the project context
        sets ``isolation: true``); otherwise the dispatcher-provided
        scratch ``workdir``.
        """
        start = time.monotonic()
        prompt = self._format_prompt(packet)

        cwd, worktree = await resolve_workdir(packet, workdir)
        try:
            cli_tools = _allowed_cli_tools(packet.allowed_tools)
            args = [self._binary, "-p", prompt, "--output-format", "json"]
            if cli_tools is not None:
                args += [_ALLOWED_TOOLS_FLAG, ",".join(cli_tools)]

            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                await proc.communicate()
                return DriverResult(
                    success=False,
                    error=f"claude_code timed out after {timeout}s",
                    duration_ms=int((time.monotonic() - start) * 1000),
                    metadata={"exit_status": "timeout"},
                )

            duration = int((time.monotonic() - start) * 1000)
            data = self._parse_output(out)
            success = proc.returncode == 0 and not data.get("is_error", False)
            return DriverResult(
                success=success,
                output=str(data.get("result", ""))[:20000],
                cost_usd=float(data.get("total_cost_usd") or 0.0),
                duration_ms=duration,
                error=None if success else (
                    str(data.get("result") or err.decode(errors="replace"))[:2000]
                    or f"exit code {proc.returncode}"
                ),
                metadata={
                    "exit_status": "ok" if success else "failed",
                    "session_id": data.get("session_id"),
                    "num_turns": data.get("num_turns"),
                    "workdir": str(cwd),
                    "isolated": worktree is not None,
                },
            )
        except FileNotFoundError:
            return DriverResult(
                success=False,
                error=f"claude_code binary {self._binary!r} not found",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            logger.error("claude_code dispatch failed: %s", e, exc_info=True)
            return DriverResult(
                success=False,
                error=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        finally:
            if worktree is not None:
                await remove_worktree(packet, worktree)

    def capabilities(self) -> list[str]:
        """Task types Claude Code handles well."""
        return ["code", "test", "review", "refactor", "docs"]

    def cost_per_task(self) -> float:
        """Estimated frontier-class cost per task (actual cost comes back
        in the CLI's JSON output)."""
        return DEFAULT_COST_PER_TASK_USD

    # ── Internals ─────────────────────────────────────────────

    @staticmethod
    def _format_prompt(packet: ContextPacket) -> str:
        """Render the context packet as a headless prompt.

        Private packets get instruction + project context only — memories
        and preferences never leave the local system. The persona's own
        system prompt (when the dispatch was pinned to one) leads the
        prompt, same as LocalDriver's system_prompt construction.
        """
        parts = []
        if packet.persona_system_prompt:
            parts.append(packet.persona_system_prompt)
        parts.append(packet.instruction)
        if packet.project_context:
            safe_project = {
                k: v for k, v in packet.project_context.items()
                if k not in ("path", "isolation")
            }
            if safe_project:
                parts.append(f"\n## Project context\n{json.dumps(safe_project, default=str)}")
        if not packet.private:
            if packet.procedures:
                parts.append(f"\n## Known procedures\n{json.dumps(packet.procedures, default=str)}")
            if packet.preferences:
                parts.append(f"\n## User preferences\n{json.dumps(packet.preferences, default=str)}")
            # Immune System: memories are trust-tiered; untrusted ones are
            # rendered inside a data fence, never as bare instructions.
            memory_block = render_memory_block(packet.memories)
            if memory_block:
                parts.append(memory_block)
        return "\n".join(parts)

    @staticmethod
    def _parse_output(out: bytes) -> dict:
        """Parse the CLI's JSON stdout; tolerate plain-text output."""
        text = (out or b"").decode(errors="replace").strip()
        if not text:
            return {}
        try:
            data = json.loads(text)
            return data if isinstance(data, dict) else {"result": data}
        except json.JSONDecodeError:
            return {"result": text}

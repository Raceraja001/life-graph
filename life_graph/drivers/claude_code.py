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
_DISALLOWED_TOOLS_FLAG = "--disallowedTools"
_PERMISSION_MODE_FLAG = "--permission-mode"

# The CLI's most restrictive non-interactive permission mode (verified
# against `claude --help`: choices are acceptEdits, auto, bypassPermissions,
# manual, dontAsk, plan). "manual" asks for approval on anything not already
# pre-approved — and in headless `-p` mode there is nobody to ask, so those
# calls are refused. Passed explicitly whenever the packet is tool-scoped so
# a host-level default (a `permissions.defaultMode` of bypassPermissions /
# acceptEdits in ~/.claude/settings.json) cannot silently widen an
# unattended dispatch beyond its persona's allowlist.
_RESTRICTIVE_PERMISSION_MODE = "manual"

# life_graph tool registry name → the SET of Claude Code CLI tool names that
# grant the same capability. The CLI has a different, coarser vocabulary in
# some places (no separate git_status/git_diff/etc. — all shell-adjacent
# operations go through "Bash") and a finer one in others (reading is Read +
# the Glob/Grep search tools; writing is Write for whole new files but Edit
# for modifying an existing one — dependency-updater's entire job is the
# latter, so mapping file_write to Write alone would leave it unable to work).
# Names with no sensible CLI equivalent (delegate_to_persona, calculator,
# get_current_datetime, inspect_system) are simply absent — an allowed_tools
# list containing only those maps to an empty CLI allowlist, which
# :meth:`ClaudeCodeDriver.dispatch` refuses outright rather than shelling
# out unscoped.
_TOOL_NAME_TO_CLI: dict[str, tuple[str, ...]] = {
    "run_command": ("Bash",),
    "git_status": ("Bash",),
    "git_log": ("Bash",),
    "git_diff": ("Bash",),
    "git_branch": ("Bash",),
    "file_read": ("Read", "Glob", "Grep"),
    "file_write": ("Write", "Edit"),
    "web_search": ("WebSearch",),
    "browse_web": ("WebFetch",),
}


# Belt-and-suspenders denylist. `--allowedTools` is a PRE-APPROVAL list, not
# a sandbox: a tool merely ABSENT from it is not thereby forbidden, it just
# falls through to the CLI's permission system (which a host
# ~/.claude/settings.json `permissions.allow` rule can answer for us).
# `--disallowedTools` IS a denial, so we also deny explicitly. We cannot
# enumerate every tool the CLI will ever ship, so this is deliberately a
# small, fixed set of the write/execute-capable tool names — the ones where
# "hint" vs. "restriction" actually matters for an unattended dispatch —
# and we deny whichever of them the persona did not earn. Read-only CLI
# tools (Read/Glob/Grep/WebSearch/WebFetch) are intentionally NOT denied:
# they carry no blast radius, and hard-denying them would newly break
# existing personas (e.g. uzhavu-ops) that this branch is meant not to
# regress.
_DENIABLE_CLI_TOOLS: tuple[str, ...] = ("Bash", "Edit", "NotebookEdit", "Write")


def _disallowed_cli_tools(cli_tools: list[str]) -> list[str]:
    """The write/exec-capable CLI tools this packet did NOT ask for.

    Complement of ``cli_tools`` within :data:`_DENIABLE_CLI_TOOLS`. May be
    empty (a persona holding every dangerous tool), in which case the caller
    omits the flag rather than passing an ambiguous empty value.
    """
    return sorted(set(_DENIABLE_CLI_TOOLS) - set(cli_tools))


def _allowed_cli_tools(allowed_tools: list[str] | None) -> list[str] | None:
    """Translate life_graph tool names into Claude Code CLI tool names.

    Returns ``None`` when ``allowed_tools`` is ``None`` (no persona scoping —
    the CLI keeps its own default permissions, matching the "no scoping"
    contract ``ContextPacket.allowed_tools`` already documents). A present
    list where every name is unmapped produces an empty list, which the
    caller treats as fail-closed.
    """
    if allowed_tools is None:
        return None
    mapped: set[str] = set()
    for name in allowed_tools:
        mapped.update(_TOOL_NAME_TO_CLI.get(name, ()))
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

        Refuses to run at all when the packet IS tool-scoped but no
        requested tool maps to a CLI tool: shelling out with an empty
        ``--allowedTools`` value has unverified CLI semantics, so the
        unambiguous fail-closed behavior is to not dispatch.
        """
        start = time.monotonic()

        cli_tools = _allowed_cli_tools(packet.allowed_tools)
        if cli_tools is not None and not cli_tools:
            logger.warning(
                "claude_code refusing task %s: allowed_tools %r maps to no CLI tool",
                packet.task_id, packet.allowed_tools,
            )
            return DriverResult(
                success=False,
                error=(
                    "No CLI-mappable tools in persona allowlist — "
                    "refusing to dispatch unscoped"
                ),
                duration_ms=int((time.monotonic() - start) * 1000),
                metadata={"exit_status": "refused_unscoped"},
            )

        prompt = self._format_prompt(packet)

        cwd, worktree = await resolve_workdir(packet, workdir)
        try:
            args = [self._binary, "-p", prompt, "--output-format", "json"]
            if cli_tools is not None:
                args += [
                    _ALLOWED_TOOLS_FLAG,
                    ",".join(cli_tools),
                    # --allowedTools is a PRE-APPROVAL list, not a sandbox:
                    # an unlisted tool call still falls through to the CLI's
                    # permission system. Pin the mode so a permissive host
                    # default cannot approve it on our behalf.
                    _PERMISSION_MODE_FLAG,
                    _RESTRICTIVE_PERMISSION_MODE,
                ]
                # ...and deny the dangerous tools outright, so the scoping
                # does not depend on the permission system answering right.
                denied = _disallowed_cli_tools(cli_tools)
                if denied:
                    args += [_DISALLOWED_TOOLS_FLAG, ",".join(denied)]

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

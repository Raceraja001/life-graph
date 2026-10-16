"""OpenCode headless driver: an open-source coding agent as a dev-task engine.

Runs ``opencode run --format json`` (OpenCode, MIT) in the task's worktree,
on a local Ollama model by default. It is an alternative to the in-house
local driver, whose own agent loop was the weak point in the recordings
(tool calls with no arguments). Which engine is better is not argued here
but measured: both are scored on the Agent scorecards.

Contract, as for every driver: it only edits the worktree it is given. The
dispatcher's verifier chain, review and approvals decide whether anything
lands. Confinement is OpenCode's own permission system, written into a
config file *outside* the worktree (so it is not part of the agent's diff):
- ``external_directory: deny`` — no reads or writes outside the worktree;
  checked against a real run in which the model tried to write elsewhere;
- ``bash`` denied unless ``driver_opencode_allow_bash`` is set, because the
  host is not sandboxed. Tests run in the verifier sandbox afterwards anyway;
- ``webfetch`` denied.
Explicit denies hold even under ``--auto``, which only auto-approves what is
not denied.

Unavailable (skipped by driver selection) until the ``opencode`` binary is
installed: ``npm install --prefix ~/.local/opencode opencode-ai`` and point
``LIFE_GRAPH_DRIVER_OPENCODE_BIN`` at ``~/.local/opencode/node_modules/.bin/opencode``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import tempfile
import time
from pathlib import Path

from life_graph.config import settings
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.steps import number
from life_graph.drivers.workdir import remove_worktree, resolve_workdir

logger = logging.getLogger(__name__)

# life_graph tool names that grant writing files (persona allow-lists).
_WRITE_TOOLS = frozenset({"file_write", "code_edit"})


def _config(packet: ContextPacket) -> dict:
    """The OpenCode config for one dispatch: provider, model and permissions."""
    model = settings.driver_opencode_model
    provider, _, model_id = model.partition("/")
    allowed = packet.allowed_tools
    can_edit = allowed is None or bool(_WRITE_TOOLS & set(allowed))
    config: dict = {
        "$schema": "https://opencode.ai/config.json",
        "permission": {
            "edit": "allow" if can_edit else "deny",
            "bash": "allow" if settings.driver_opencode_allow_bash else "deny",
            "webfetch": "deny",
            "external_directory": "deny",
        },
        "autoupdate": False,
        "share": "disabled",
    }
    if provider == "ollama":
        config["provider"] = {
            "ollama": {
                "npm": "@ai-sdk/openai-compatible",
                "name": "Ollama",
                "options": {"baseURL": settings.driver_opencode_ollama_base},
                "models": {model_id: {}},
            }
        }
    return config


def parse_events(text: str) -> tuple[str, list[dict], dict]:
    """``opencode run --format json`` stdout -> (final text, steps, metadata).

    Events (OpenCode 1.19): ``step_start`` / ``step_finish`` frame each model
    turn; ``text`` carries what the agent said; ``tool_use`` carries a whole
    tool call with its input and its output or error; ``error`` a failure.
    """
    steps: list[dict] = []
    texts: list[str] = []
    meta: dict = {"turns": 0}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        etype = event.get("type")
        part = event.get("part") or {}
        at = event.get("timestamp")
        at_iso = (
            time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(at / 1000)) + "Z"
            if isinstance(at, (int, float))
            else None
        )
        meta.setdefault("session_id", event.get("sessionID"))
        if etype == "step_finish":
            meta["turns"] += 1
        elif etype == "text" and part.get("text"):
            texts.append(part["text"])
            steps.append({"kind": "text", "content": part["text"], "at": at_iso})
        elif etype == "tool_use":
            state = part.get("state") or {}
            ref = part.get("callID")
            steps.append(
                {
                    "kind": "tool_call",
                    "tool": part.get("tool"),
                    "content": json.dumps(state.get("input"), default=str),
                    "ref": ref,
                    "at": at_iso,
                }
            )
            failed = state.get("status") == "error"
            result = {
                "kind": "tool_result",
                "tool": part.get("tool"),
                "content": str(state.get("error") if failed else state.get("output") or ""),
                "ref": ref,
                "at": at_iso,
            }
            if failed:
                result["is_error"] = True
            steps.append(result)
        elif etype == "error":
            error = event.get("error") or part
            steps.append({"kind": "error", "content": json.dumps(error, default=str), "at": at_iso})
            meta["error"] = json.dumps(error, default=str)[:500]
    return (texts[-1] if texts else ""), number(steps), meta


class OpencodeDriver:
    """OpenCode in headless mode, as an AgentDriver."""

    name = "opencode"
    max_concurrency = 1  # one local model on one GPU

    def __init__(self, binary: str | None = None) -> None:
        self._binary = binary or settings.driver_opencode_bin

    @property
    def dispatch_timeout(self) -> int:
        return settings.driver_opencode_timeout_seconds

    async def available(self) -> bool:
        found = shutil.which(self._binary) is not None or Path(self._binary).is_file()
        if not found:
            logger.debug("opencode unavailable: %r not found", self._binary)
        return found

    async def dispatch(
        self, packet: ContextPacket, workdir: Path, timeout: int = 300
    ) -> DriverResult:
        start = time.monotonic()
        cwd, worktree = await resolve_workdir(packet, workdir)
        config_dir = Path(tempfile.mkdtemp(prefix="lg-opencode-"))
        try:
            config_file = config_dir / "opencode.json"
            config_file.write_text(json.dumps(_config(packet)))
            prompt = self._prompt(packet)
            env = {**os.environ, "OPENCODE_CONFIG": str(config_file)}
            argv = [
                self._binary,
                "run",
                "--format",
                "json",
                "--auto",
                "-m",
                settings.driver_opencode_model,
                "--dir",
                str(cwd),
                prompt,
            ]
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    cwd=str(cwd),
                    env=env,
                    # OpenCode waits on an open stdin: closed, it runs headless.
                    stdin=asyncio.subprocess.DEVNULL,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            except FileNotFoundError:
                return DriverResult(
                    success=False,
                    error=f"opencode binary {self._binary!r} not found",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            # Read as it streams: communicate() under wait_for dropped everything
            # on a timeout, so a 20-minute run left no steps (task cce99bf5).
            out_buf, err_buf = bytearray(), bytearray()

            async def drain(stream: asyncio.StreamReader, buf: bytearray) -> None:
                while chunk := await stream.read(65536):
                    buf.extend(chunk)

            readers = [
                asyncio.ensure_future(drain(proc.stdout, out_buf)),
                asyncio.ensure_future(drain(proc.stderr, err_buf)),
            ]
            try:
                await asyncio.wait_for(proc.wait(), timeout=timeout)
            except TimeoutError:
                proc.kill()
                await proc.wait()
                # A child still holding the pipe would keep the readers open.
                _, pending = await asyncio.wait(readers, timeout=5)
                for r in pending:
                    r.cancel()
                text, steps, meta = parse_events(out_buf.decode(errors="replace"))
                return DriverResult(
                    success=False,
                    output=text[:20000],
                    error=f"opencode timed out after {timeout}s",
                    duration_ms=int((time.monotonic() - start) * 1000),
                    metadata={
                        "exit_status": "timeout",
                        "driver": self.name,
                        "model": settings.driver_opencode_model,
                        "num_turns": meta.get("turns"),
                        "steps": steps,
                        "workdir": str(cwd),
                    },
                )
            await asyncio.gather(*readers)
            out, err = bytes(out_buf), bytes(err_buf)
            text, steps, meta = parse_events(out.decode(errors="replace"))
            success = proc.returncode == 0 and "error" not in meta
            return DriverResult(
                success=success,
                output=text[:20000],
                cost_usd=0.0,  # local model; a paid provider is not metered here
                duration_ms=int((time.monotonic() - start) * 1000),
                error=None
                if success
                else (
                    meta.get("error") or err.decode(errors="replace")[-2000:] or "opencode failed"
                ),
                metadata={
                    "driver": self.name,
                    "model": settings.driver_opencode_model,
                    "session_id": meta.get("session_id"),
                    "num_turns": meta.get("turns"),
                    "steps": steps,
                    "workdir": str(cwd),
                    "isolated": worktree is not None,
                    "exit_status": "ok" if success else "failed",
                },
            )
        finally:
            shutil.rmtree(config_dir, ignore_errors=True)
            if worktree is not None:
                await remove_worktree(packet, worktree)

    @staticmethod
    def _prompt(packet: ContextPacket) -> str:
        parts = []
        if packet.persona_system_prompt:
            parts.append(packet.persona_system_prompt)
        parts.append(packet.instruction)
        parts.append(
            "\nWork only inside the current directory: it is an isolated copy of the "
            "project. Your changes are verified by the project's own tests after you "
            "finish, so make the change complete, then stop."
        )
        if not settings.driver_opencode_allow_bash:
            # Without this, qwen3-coder spent a 20-minute run writing test-runner
            # scripts it could not execute (task cce99bf5, 2026-10-16).
            parts.append(
                "You cannot run commands or tests here. Do not write runner or scratch "
                "files: change only the files the task needs."
            )
        return "\n\n".join(parts)
        return "\n\n".join(parts)

    def capabilities(self) -> list[str]:
        return ["code", "code_change", "test", "refactor", "docs"]

    def cost_per_task(self) -> float:
        return 0.0

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
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from life_graph.config import settings
from life_graph.drivers import self_check
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.steps import number
from life_graph.drivers.workdir import diff_against_head, remove_worktree, resolve_workdir

logger = logging.getLogger(__name__)


@dataclass
class _Run:
    returncode: int | None
    out: bytes
    err: bytes
    timed_out: bool = False


# life_graph tool names that grant writing files (persona allow-lists).
_WRITE_TOOLS = frozenset({"file_write", "code_edit"})


def _can_run_tests(packet: ContextPacket) -> bool:
    """A Python or JVM project, with the sandbox on and run_tests in the persona's tools."""
    from life_graph.services import sandbox

    allowed = packet.allowed_tools
    ctx = packet.project_context or {}
    return (
        (allowed is None or "run_tests" in allowed)
        and sandbox.enabled()
        and (ctx.get("sandbox_toolchain") or "python").strip().lower() in ("python", "jvm")
    )


def _run_tests_server(packet: ContextPacket, workdir: Path) -> dict | None:
    """OpenCode's way to run tests: the sandbox-only run_tests tool, served
    over MCP (tools/run_tests_mcp.py). Bash stays denied."""
    if not _can_run_tests(packet):
        return None
    ctx = packet.project_context or {}
    # The server starts in the worktree, which has no .env: pass the sandbox
    # settings it needs explicitly.
    env = {
        "LG_RUN_TESTS_WORKDIR": str(workdir),
        "LG_RUN_TESTS_SETUP": ctx.get("sandbox_setup") or "",
        "LG_RUN_TESTS_TOOLCHAIN": ctx.get("sandbox_toolchain") or "python",
        "LG_RUN_TESTS_COMMAND": ctx.get("sandbox_test_command") or "",
        "LIFE_GRAPH_VERIFIER_SANDBOX": settings.verifier_sandbox,
        "LIFE_GRAPH_VERIFIER_SANDBOX_IMAGE": settings.verifier_sandbox_image,
        "LIFE_GRAPH_VERIFIER_SANDBOX_JVM_IMAGE": settings.verifier_sandbox_jvm_image,
        "LIFE_GRAPH_VERIFIER_SANDBOX_JVM_MEMORY": str(settings.verifier_sandbox_jvm_memory),
        "LIFE_GRAPH_VERIFIER_SANDBOX_CACHE_DIR": str(settings.verifier_sandbox_cache_dir),
        "LIFE_GRAPH_VERIFIER_SANDBOX_CPUS": str(settings.verifier_sandbox_cpus),
        "LIFE_GRAPH_VERIFIER_SANDBOX_MEMORY": str(settings.verifier_sandbox_memory),
    }
    return {
        "type": "local",
        # -I: OpenCode starts the server in the worktree, and `python -m` puts
        # the current directory first on sys.path. Task 4b3249d4 imported the
        # worktree's life_graph (cut from master, no run_tests_mcp) and the
        # server died; on the life-graph project an agent could also rewrite
        # the very tool that keeps tests in the sandbox. Isolated mode imports
        # only the installed life_graph and ignores PYTHON* variables.
        "command": [sys.executable, "-I", "-m", "life_graph.tools.run_tests_mcp"],
        "environment": env,
        "enabled": True,
    }


def _config(packet: ContextPacket, workdir: Path | None = None) -> dict:
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
    server = _run_tests_server(packet, workdir) if workdir is not None else None
    if server is not None:
        config["mcp"] = {"lg_tests": server}
    return config


def parse_events(text: str) -> tuple[str, list[dict], dict]:
    """``opencode run --format json`` stdout -> (all text, steps, metadata).

    Events (OpenCode 1.19): ``step_start`` / ``step_finish`` frame each model
    turn; ``text`` carries what the agent said; ``tool_use`` carries a whole
    tool call with its input and its output or error; ``error`` a failure.
    Every text part is kept, not only the last: task 81de2480 wrote its
    ``## Spec`` and its ``## Understanding`` in separate parts, and keeping
    the last one lost the spec.
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
    return "\n\n".join(texts), number(steps), meta


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

    async def _invoke(
        self, prompt: str, cwd: Path, env: dict, timeout: int, session_id: str | None
    ) -> _Run:
        """One ``opencode run``; with *session_id*, continues that session."""
        argv = [self._binary, "run", "--format", "json", "--auto"]
        argv += ["-m", settings.driver_opencode_model, "--dir", str(cwd)]
        if session_id:
            argv += ["--session", session_id]
        proc = await asyncio.create_subprocess_exec(
            *argv,
            prompt,
            cwd=str(cwd),
            env=env,
            # OpenCode waits on an open stdin: closed, it runs headless.
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
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
            return _Run(None, bytes(out_buf), bytes(err_buf), timed_out=True)
        await asyncio.gather(*readers)
        return _Run(proc.returncode, bytes(out_buf), bytes(err_buf))

    async def dispatch(
        self, packet: ContextPacket, workdir: Path, timeout: int = 300
    ) -> DriverResult:
        start = time.monotonic()
        cwd, worktree = await resolve_workdir(packet, workdir)
        config_dir = Path(tempfile.mkdtemp(prefix="lg-opencode-"))
        try:
            config_file = config_dir / "opencode.json"
            config_file.write_text(json.dumps(_config(packet, cwd)))
            prompt = self._prompt(packet)
            env = {**os.environ, "OPENCODE_CONFIG": str(config_file)}
            deadline = start + timeout
            steps: list[dict] = []
            texts: list[str] = []
            session_id: str | None = None
            turns = 0
            self_checks = 0
            while True:
                try:
                    run = await self._invoke(
                        prompt, cwd, env, max(1, int(deadline - time.monotonic())), session_id
                    )
                except FileNotFoundError:
                    return DriverResult(
                        success=False,
                        error=f"opencode binary {self._binary!r} not found",
                        duration_ms=int((time.monotonic() - start) * 1000),
                    )
                text, run_steps, meta = parse_events(run.out.decode(errors="replace"))
                steps += run_steps
                if text:
                    texts.append(text)
                session_id = meta.get("session_id") or session_id
                turns += meta.get("turns") or 0
                if run.timed_out:
                    return DriverResult(
                        success=False,
                        output="\n\n".join(texts)[-20000:],
                        error=f"opencode timed out after {timeout}s",
                        duration_ms=int((time.monotonic() - start) * 1000),
                        metadata={
                            "exit_status": "timeout",
                            "driver": self.name,
                            "model": settings.driver_opencode_model,
                            "num_turns": turns,
                            "steps": number(steps),
                            "workdir": str(cwd),
                            "self_checks": self_checks,
                        },
                    )
                success = run.returncode == 0 and "error" not in meta
                if not success or self_checks >= self_check.MAX_SELF_CHECKS or not session_id:
                    break
                # The harness runs the tests the agent added or changed and, if
                # they fail, continues the same session with the output
                # (drivers/self_check.py).
                feedback = await self_check.check(
                    cwd, packet.project_context or {}, packet.instruction
                )
                if (
                    not feedback
                    and packet.task_type in ("code", "code_change")
                    and (cwd / ".git").exists()
                    and not await diff_against_head(cwd)
                ):
                    # Task 25df9f39 read twelve files, decided nothing was
                    # needed and stopped; the dispatcher then failed it as
                    # no_change without the agent ever being told.
                    from life_graph.drivers.local import NO_NET_CHANGE_NUDGE

                    feedback = NO_NET_CHANGE_NUDGE
                if not feedback or time.monotonic() > deadline - 60:
                    break
                self_checks += 1
                prompt = feedback
            err = run.err
            return DriverResult(
                success=success,
                # Every turn's text: the session may be continued by self-checks.
                output="\n\n".join(texts)[-20000:],
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
                    "session_id": session_id,
                    "num_turns": turns,
                    "steps": number(steps),
                    "workdir": str(cwd),
                    "isolated": worktree is not None,
                    "exit_status": "ok" if success else "failed",
                    "self_checks": self_checks,
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
            tests = (
                "To run a test, use the run_tests tool (lg_tests_run_tests) and fix it "
                "until it passes."
                if _can_run_tests(packet)
                else "You cannot run tests here either."
            )
            parts.append(
                f"You cannot run shell commands. {tests} Do not write runner or scratch "
                "files: change only the files the task needs, including any new test file "
                "it names."
            )
        return "\n\n".join(parts)

    def capabilities(self) -> list[str]:
        return ["code", "code_change", "test", "refactor", "docs"]

    def cost_per_task(self) -> float:
        return 0.0

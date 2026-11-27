"""The common shape of a subscription coding-CLI driver (codex, gemini).

Each CLI driver supplies its argv, its event parser and its sign-in check;
this base runs the rest the same way for both, and the same way the
claude_code driver does on the host:

    resolve the workdir -> build a prompt with no personal data -> run the CLI
    (host_exec rules, prompt on stdin, live events) -> parse its JSON lines into
    driver-neutral steps -> classify a failure -> remove the worktree.

Personal data (CHARTER invariant 7): both CLIs send everything to a cloud
provider, so memories, preferences and procedures are never in the prompt,
whatever ``packet.private`` says. The task, the persona prompt, the project
metadata and the code are what leave the machine, as with the cloud driver.
"""

from __future__ import annotations

import json
import logging
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.cli_failure import classify_failure
from life_graph.drivers.cli_run import CliProbe, cli_env, probe, resolve_binary, run_cli
from life_graph.drivers.steps import number
from life_graph.drivers.workdir import remove_worktree, resolve_workdir
from life_graph.services.dev import task_events

if TYPE_CHECKING:
    from datetime import datetime

logger = logging.getLogger(__name__)

# life_graph tool names that grant writing files (as in drivers/opencode.py).
WRITE_TOOLS = frozenset({"file_write", "code_edit"})

MAX_OUTPUT_CHARS = 20_000


@dataclass
class ParsedRun:
    """Everything one CLI run's event stream said, in driver-neutral terms."""

    texts: list[str] = field(default_factory=list)
    steps: list[dict] = field(default_factory=list)
    session_id: str | None = None
    model: str | None = None
    turns: int = 0
    usage: dict = field(default_factory=dict)
    completed: bool = False  # the CLI reported a successful end of the run
    final_error: str = ""
    warnings: list[str] = field(default_factory=list)
    rate_limits: list[dict] = field(default_factory=list)
    rate_limit_rejected: bool = False
    rate_limit_resets: list[str] = field(default_factory=list)
    lines: int = 0

    def add_usage(self, **counts: int | None) -> None:
        for key, value in counts.items():
            if isinstance(value, int) and not isinstance(value, bool):
                self.usage[key] = self.usage.get(key, 0) + value


class EventParser:
    """Feed it stdout lines; it returns the new steps and keeps the totals."""

    def __init__(self) -> None:
        self.run = ParsedRun()

    def feed(self, line: str) -> list[dict]:
        text = (line or "").strip()
        if not text.startswith("{"):
            return []
        try:
            event = json.loads(text)
        except json.JSONDecodeError:
            return []
        if not isinstance(event, dict):
            return []
        self.run.lines += 1
        steps = self.on_event(event)
        self.run.steps.extend(steps)
        return steps

    def feed_text(self, text: str) -> None:
        for line in (text or "").splitlines():
            self.feed(line)

    def on_event(self, event: dict) -> list[dict]:  # pragma: no cover - abstract
        raise NotImplementedError

    def finish(self) -> list[dict]:
        """Steps still buffered when the stream ended; recorded in ``run.steps``."""
        return []


def needs_read_only(packet: ContextPacket) -> bool:
    """A plan, or a persona whose tools cannot write: the CLI runs read-only."""
    if packet.task_type == "plan":
        return True
    allowed = packet.allowed_tools
    return allowed is not None and not (WRITE_TOOLS & set(allowed))


def build_prompt(packet: ContextPacket, *, read_only: bool) -> str:
    """The task as the CLI sees it: no memories, preferences or procedures."""
    parts: list[str] = []
    if packet.persona_system_prompt:
        parts.append(packet.persona_system_prompt)
    parts.append(packet.instruction)
    safe_project = {
        k: v for k, v in (packet.project_context or {}).items() if k not in ("path", "isolation")
    }
    if safe_project:
        parts.append(f"## Project context\n{json.dumps(safe_project, default=str)}")
    if read_only:
        parts.append("Do not modify any files: this run is read-only.")
    else:
        parts.append(
            "Work only inside the current directory: it is an isolated copy of the "
            "project. Your changes are verified by the project's own tests after you "
            "finish, so make the change complete, then stop."
        )
    return "\n\n".join(parts)


class _LiveSteps:
    """Each stdout line -> parser -> live session events (as claude_code's _LiveStream)."""

    def __init__(self, packet: ContextPacket, parser: EventParser, driver: str) -> None:
        self.tenant = packet.tenant_id
        self.task = packet.task_id
        self.parser = parser
        self.driver = driver

    def __call__(self, line: str) -> None:
        steps = self.parser.feed(line)
        if not steps:
            return
        for step in steps:
            task_events.emit(
                self.tenant,
                self.task,
                step["kind"],
                step.get("content") or "",
                data={k: step[k] for k in ("tool", "is_error", "ref") if step.get(k)},
                source="agent",
            )


class SubscriptionCliDriver:
    """Base for a coding CLI that runs on the owner's subscription login."""

    name: ClassVar[str] = ""
    billing: ClassVar[str] = "subscription"
    max_concurrency: ClassVar[int] = 1  # one subscription's limits; Phase 3b adds a pool
    login_hint: ClassVar[str] = ""

    def __init__(self, binary: str | None = None) -> None:
        self._binary_override = binary

    # ── Per-CLI hooks ──────────────────────────────────────────

    @property
    def enabled(self) -> bool:  # pragma: no cover - abstract
        raise NotImplementedError

    @property
    def binary(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    @property
    def model(self) -> str:  # pragma: no cover - abstract
        raise NotImplementedError

    @property
    def dispatch_timeout(self) -> int:  # pragma: no cover - abstract
        raise NotImplementedError

    def env_extra(self) -> dict[str, str]:
        """Non-secret variables this CLI needs (its own config location)."""
        return {}

    async def login_check(self, path: str, env: dict[str, str]) -> bool | None:  # pragma: no cover
        raise NotImplementedError

    def refusal(self, packet: ContextPacket) -> DriverResult | None:
        """A reason not to run this packet at all, or None."""
        return None

    def build_argv(
        self, binary: str, cwd: Path, *, read_only: bool, scratch: Path
    ) -> tuple[list[str], dict[str, str]]:  # pragma: no cover - abstract
        """(argv, extra env) for one run; *scratch* is a private temp dir."""
        raise NotImplementedError

    def new_parser(self) -> EventParser:  # pragma: no cover - abstract
        raise NotImplementedError

    def run_metadata(self, *, read_only: bool) -> dict:
        """Driver-specific metadata (sandbox mode, approval mode...)."""
        return {}

    # ── Protocol ──────────────────────────────────────────────

    async def detect(self, force: bool = False) -> CliProbe:
        """Installed / version / signed in, cached (drivers/cli_run.py)."""
        return await probe(
            self.name,
            self.binary,
            login_check=self.login_check,
            login_hint=self.login_hint,
            env_extra=self.env_extra(),
            force=force,
        )

    async def available(self) -> bool:
        """Enabled, installed, and not known to be signed out."""
        if not self.enabled:
            logger.debug("%s unavailable: off (driver_%s_enabled=false)", self.name, self.name)
            return False
        found = await self.detect()
        if not found.installed:
            logger.debug("%s unavailable: %s", self.name, found.hint)
            return False
        if found.logged_in is False:
            logger.debug("%s unavailable: signed out (%s)", self.name, self.login_hint)
            return False
        return True

    async def describe(self) -> dict:
        """What GET /kernel/drivers shows about this driver's readiness."""
        found = await self.detect()
        return {"enabled": self.enabled, "billing": self.billing, **found.as_dict()}

    def capabilities(self) -> list[str]:
        return ["code", "code_change", "test", "review", "refactor", "docs"]

    def cost_per_task(self) -> float:
        """Marginal USD per task: $0 on a subscription (risk D4: not budgeted)."""
        return 0.0

    async def dispatch(
        self,
        packet: ContextPacket,
        workdir: Path,
        timeout: int = 300,
        *,
        now: datetime | None = None,
    ) -> DriverResult:
        start = time.monotonic()

        def elapsed() -> int:
            return int((time.monotonic() - start) * 1000)

        refused = self.refusal(packet)
        if refused is not None:
            refused.duration_ms = elapsed()
            return refused
        binary = resolve_binary(self.binary)
        if binary is None:
            return DriverResult(
                success=False,
                error=f"{self.name} binary {self.binary!r} not found",
                duration_ms=elapsed(),
                metadata={"exit_status": "not_installed", "driver": self.name},
            )
        read_only = needs_read_only(packet)
        cwd, worktree = await resolve_workdir(packet, workdir)
        scratch = Path(tempfile.mkdtemp(prefix=f"lg-{self.name}-"))
        try:
            argv, extra = self.build_argv(binary, cwd, read_only=read_only, scratch=scratch)
            env = cli_env(binary, {**self.env_extra(), **extra})
            parser = self.new_parser()
            live = _LiveSteps(packet, parser, self.name)
            try:
                run = await run_cli(
                    argv,
                    cwd=cwd,
                    env=env,
                    timeout=timeout,
                    stdin=build_prompt(packet, read_only=read_only),
                    on_stdout_line=live,
                )
            except FileNotFoundError:
                return DriverResult(
                    success=False,
                    error=f"{self.name} binary {binary!r} not found",
                    duration_ms=elapsed(),
                    metadata={"exit_status": "not_installed", "driver": self.name},
                )
            if parser.run.lines == 0:
                # No live lines (a stand-in process without pipes): parse afterwards.
                parser.feed_text(run.out.decode(errors="replace"))
            parser.finish()
            parsed = parser.run
            stderr = run.err.decode(errors="replace")
            success = not run.timed_out and run.returncode == 0 and parsed.completed
            output = "\n\n".join(parsed.texts)[-MAX_OUTPUT_CHARS:]
            metadata: dict = {
                "driver": self.name,
                "billing": self.billing,
                "model": parsed.model or self.model or None,
                "session_id": parsed.session_id,
                "num_turns": parsed.turns,
                "usage": parsed.usage or None,
                "steps": number(parsed.steps, tool_names=True),
                "workdir": str(cwd),
                "isolated": worktree is not None,
                "boundary": "host",
                "read_only": read_only,
                **self.run_metadata(read_only=read_only),
            }
            if parsed.rate_limits:
                metadata["rate_limits"] = parsed.rate_limits
            if run.timed_out:
                metadata["exit_status"] = "timeout"
                return DriverResult(
                    success=False,
                    output=output,
                    error=f"{self.name} timed out after {timeout}s",
                    duration_ms=elapsed(),
                    metadata=metadata,
                )
            if success:
                metadata["exit_status"] = "ok"
                return DriverResult(
                    success=True, output=output, cost_usd=0.0, duration_ms=elapsed(),
                    metadata=metadata,
                )  # fmt: skip
            failure = classify_failure(
                final_error=parsed.final_error,
                warnings=parsed.warnings,
                stderr=stderr,
                exit_code=run.returncode,
                rate_limit_resets=parsed.rate_limit_resets,
                rejected=parsed.rate_limit_rejected,
                login_hint=self.login_hint,
                now=now,
            )
            metadata["failure"] = failure
            metadata["exit_status"] = failure["kind"] if failure["kind"] != "other" else "failed"
            error = failure.get("message") or f"{self.name} failed"
            if failure["kind"] == "auth":
                error = f"{error} ({self.login_hint})" if self.login_hint else error
            elif failure["kind"] == "rate_limited" and failure.get("resets_at"):
                error = f"{error} (resets {failure['resets_at']})"
            return DriverResult(
                success=False, output=output, error=error, duration_ms=elapsed(),
                metadata=metadata,
            )  # fmt: skip
        finally:
            shutil.rmtree(scratch, ignore_errors=True)
            if worktree is not None:
                await remove_worktree(packet, worktree)

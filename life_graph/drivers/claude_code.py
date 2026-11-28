"""Claude Code headless driver — wrap, don't rebuild (strategic-decision.md).

Invokes the Claude Code CLI in headless mode (``claude -p "<packet>"
--output-format stream-json --verbose``) with ``cwd`` set to the project
path — or an isolated git worktree when the project context asks for
isolation — and normalizes the final result event to a
:class:`DriverResult`, with every step of the run in ``metadata["steps"]``
(see drivers/steps.py).

Graceful degradation: when the ``claude`` binary is not installed on
this host, :meth:`available` returns False and the dispatcher skips
this driver (same pattern as the era-4 advisor's missing API keys).
"""

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import json
import logging
import os
import re
import shutil
import time
from pathlib import Path

from life_graph.config import settings
from life_graph.drivers import accounts_hook
from life_graph.drivers.base import ContextPacket, DriverResult
from life_graph.drivers.cli_failure import classify_failure
from life_graph.drivers.host_exec import (
    STREAM_LIMIT,
    communicate_streaming,
    host_driver_env,
    kill_process_group,
)
from life_graph.drivers.steps import claude_event_steps, parse_claude_stream
from life_graph.drivers.workdir import remove_worktree, resolve_workdir
from life_graph.services.agent_accounts.limits import claude_windows
from life_graph.services.dev import sandbox, sandbox_deps, sandbox_git

logger = logging.getLogger(__name__)

DEFAULT_COST_PER_TASK_USD = 0.10  # frontier cost class; actual cost read from CLI output

LOGIN_HINT = "run `claude auth login`"

# A Claude session id (a UUID); anything else is refused before argv.
_SESSION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]{7,63}$")

_ALLOWED_TOOLS_FLAG = "--allowedTools"
_DISALLOWED_TOOLS_FLAG = "--disallowedTools"
_PERMISSION_MODE_FLAG = "--permission-mode"
# Host mode only. Verified against `claude --help` (2.1.x) and by hand
# (2026-11-25): it ignores user, project and local settings files and
# confines Read/Glob/Grep (and Write/Edit) to the working directory. A read
# of a file outside it, or of a symlink in it that points outside, is denied.
# It also removes Bash and WebFetch unless --tools names them.
_RESTRICTED_FLAG = "--restricted"

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
    "code_read": ("Read", "Glob", "Grep"),
    "code_search": ("Grep", "Glob"),
    "code_list": ("Glob",),
    "code_edit": ("Write", "Edit"),
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
# regress. On the host that is not true (see _HOST_DENIED_CLI_TOOLS below).
_DENIABLE_CLI_TOOLS: tuple[str, ...] = ("Bash", "Edit", "NotebookEdit", "Write")

# Host mode (driver_claude_sandbox=none): the CLI runs as the API's user, so
# a read tool can reach ~/.ssh or a .env, and a web tool can send what it
# read anywhere (Stage 0, 2026-11-25). On the host the web tools are always
# denied, and with the shell denied the run gets --restricted, which keeps
# the file tools inside the working directory. In a container (task) none of
# this applies: the worktree is the only host path and egress is allowlisted.
_HOST_DENIED_CLI_TOOLS: tuple[str, ...] = ("WebFetch", "WebSearch")


def _permission_args(
    cli_tools: list[str] | None, *, host_mode: bool, host_shell_denied: bool
) -> list[str]:
    """The CLI's permission flags for this dispatch.

    *cli_tools* is the persona's CLI allowlist (``None`` = unscoped). On the
    host (*host_mode*) the web tools are denied, and, unless the operator
    allowed the host shell, ``--restricted`` confines the file tools to the
    working directory. ``--restricted`` would also remove Bash, so it is
    left off when the host shell is allowed; that opt-in already means the
    agent can read anything the user can.
    """
    args: list[str] = []
    denied: set[str] = set(_HOST_DENIED_CLI_TOOLS) if host_mode else set()
    if host_shell_denied:
        denied.add("Bash")
    if cli_tools is not None:
        args += [
            _ALLOWED_TOOLS_FLAG,
            ",".join(cli_tools),
            # --allowedTools is a PRE-APPROVAL list, not a sandbox: an
            # unlisted tool call still falls through to the CLI's permission
            # system. Pin the mode so a permissive host default cannot
            # approve it on our behalf.
            _PERMISSION_MODE_FLAG,
            _RESTRICTIVE_PERMISSION_MODE,
        ]
        # ...and deny the dangerous tools outright, so the scoping does not
        # depend on the permission system answering right.
        denied.update(_disallowed_cli_tools(cli_tools))
    # Unscoped dispatch: the CLI's own permissions decide, which a host
    # settings.json can widen. The host denials apply regardless.
    if denied:
        args += [_DISALLOWED_TOOLS_FLAG, ",".join(sorted(denied))]
    if host_mode and host_shell_denied:
        args.append(_RESTRICTED_FLAG)
    return args


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


def _api_key() -> str | None:
    """The API key when ``driver_claude_code_auth = api_key``, else None (personal login).

    A service sold to others should not run on one person's subscription
    login; it needs Anthropic API access under commercial terms. This is the
    switch. The key comes from ``ANTHROPIC_API_KEY`` (or the setting), and
    api_key mode with no key is an error rather than a quiet fallback to the
    personal login.
    """
    if settings.driver_claude_code_auth != "api_key":
        return None
    key = os.environ.get("ANTHROPIC_API_KEY") or settings.driver_claude_code_api_key
    if not key:
        raise RuntimeError("driver_claude_code_auth=api_key but no ANTHROPIC_API_KEY is set")
    return key


_NO_SANDBOX_LOGIN = (
    "claude_code sandbox needs a long-lived login: run `claude setup-token` and set "
    "LIFE_GRAPH_DRIVER_CLAUDE_CODE_OAUTH_TOKEN. Copying ~/.claude into the container "
    "revokes the host's own login when the CLI refreshes it (docs/OPERATIONS.md, "
    "'Claude login for sandboxed runs')"
)


def _oauth_token() -> str | None:
    """The long-lived login (``claude setup-token``) for a sandboxed run, if set.

    Stripped: a stray space or newline pasted into .env would otherwise fail
    as an unexplained 401.
    """
    raw = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or settings.driver_claude_code_oauth_token
    return (raw or "").strip() or None


# Always set in the task runtime: tool caches live on the container's /tmp,
# and uv never reaches for the network (the egress allowlist would refuse it).
_TOOL_CACHE_ENV = {
    "PYTEST_ADDOPTS": "-p no:cacheprovider",
    "RUFF_NO_CACHE": "true",
    "MYPY_CACHE_DIR": "/tmp/.mypy_cache",
    "UV_CACHE_DIR": "/tmp/.uv-cache",
    "UV_OFFLINE": "1",
    "UV_PYTHON_DOWNLOADS": "never",
}

# The image's own PATH after whatever a mounted environment puts first.
_BASE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Set when the project's environment is mounted at /venv: its tools come
# first, `uv run` uses it as is (no sync into the read-only mount, no .venv
# created in the worktree), and the project imports from the worktree the way
# the verifiers import it (sandbox.py, PYTHONPATH=/work:/work/src).
_PROJECT_ENV_VARS = {
    "VIRTUAL_ENV": sandbox.VENV,
    "PATH": f"{sandbox.VENV}/bin:{_BASE_PATH}",
    "PYTHONPATH": f"{sandbox.WORK}:{sandbox.WORK}/src",
    "UV_PROJECT_ENVIRONMENT": sandbox.VENV,
    "UV_NO_SYNC": "1",
}

# The only names a dependency plan (sandbox_deps.DepsPlan.env) may set in the
# agent's container: tool cache locations and telemetry opt-outs. Anything
# else in a plan is dropped (and logged) -- a plan never sets PATH, HOME, the
# proxy, a Claude variable or a secret; the spec validator still checks values.
_DEPS_ENV_ALLOWED = frozenset(
    {
        "BUN_INSTALL_CACHE_DIR",
        "BUN_RUNTIME_TRANSPILER_CACHE_PATH",
        "XDG_CACHE_HOME",
        "DO_NOT_TRACK",
    }
)
_CONTAINER_PATH_UNSAFE = re.compile(r"[:,=\s\x00\"']")

# What the agent is told when a Bun project's dependencies are mounted
# (``--append-system-prompt``; the Python env needs no note, its tools are
# where an agent looks for them).
_DEPS_NOTE = (
    "Project toolchain: Bun. `bun` is on PATH, and the project's dependencies are already "
    "installed and mounted READ-ONLY at: {targets}. Run the project's scripts and tests with "
    "them (`bun run <script>`, `bun test`, binaries in node_modules/.bin are on PATH). You "
    "cannot install, add, remove or upgrade packages here: `bun add` / `bun install` fail on "
    "the read-only mounts and there is no registry access. If the task needs a dependency "
    "change, propose it in the diff (package.json, plus bun.lock if you can) and say so in "
    "your summary; the environment is rebuilt from the manifests when the change is verified. "
    "Never commit node_modules."
)


# What the agent is told when the worktree's git metadata is mounted
# (task_runtime._git_binds / sandbox_git): read-only, so reads work and
# writes do not; Life Graph commits on the host.
GIT_NOTE = (
    "Git in this container is READ-ONLY: `git status`, `git diff`, `git log`, `git show` and "
    "`git blame` work on /work, but the repository metadata is mounted read-only, so "
    "`git add`, `git commit`, `git stash`, `git checkout`/`switch`, branch or tag changes "
    "and anything that takes the index lock fail -- that is expected, not a broken worktree. "
    "Do not try to repair or re-initialise git and do not commit: leave your changes in the "
    "working tree; Life Graph reviews and commits them on the host. There are no remotes "
    "(no fetch, pull or push)."
)


def _under_work(path: str) -> bool:
    """A container path strictly below /work, with nothing that changes its meaning."""
    parts = path.split("/")
    return (
        path.startswith(f"{sandbox.WORK}/")
        and ".." not in parts
        and "." not in parts[1:]
        and not _CONTAINER_PATH_UNSAFE.search(path)
    )


def _checked_deps_plan(plan: sandbox_deps.DepsPlan) -> sandbox_deps.DepsPlan:
    """*plan* with its env cut to the allowlist; raises when a mount or PATH entry is wrong.

    The runtime's bind validator still checks every source; this checks what
    only the driver knows: targets and PATH entries live under the worktree.
    """
    if plan.toolchain != "bun":
        raise sandbox_deps.DepsUnavailableError(f"plan is for {plan.toolchain!r}, not bun")
    if not plan.mounts:
        raise sandbox_deps.DepsUnavailableError("plan mounts nothing")
    targets = [m.target for m in plan.mounts]
    if len(set(targets)) != len(targets):
        raise sandbox_deps.DepsUnavailableError("plan mounts one target twice")
    for target in (*targets, *plan.path_prepend):
        if not _under_work(target):
            raise sandbox_deps.DepsUnavailableError(f"plan path {target!r} is not under /work")
    dropped = sorted(set(plan.env) - _DEPS_ENV_ALLOWED)
    if dropped:
        logger.warning("claude_code: dependency plan env not passed: %s", ", ".join(dropped))
    env = {k: v for k, v in plan.env.items() if k in _DEPS_ENV_ALLOWED}
    return dataclasses.replace(plan, env=env)


def _deps_env(plan: sandbox_deps.DepsPlan) -> dict[str, str]:
    """The container env for a (checked) dependency plan: its PATH first, then the image's."""
    return {**plan.env, "PATH": ":".join((*plan.path_prepend, _BASE_PATH))}


def _git_mountable(cwd: Path) -> bool:
    """Whether the task runtime will mount *cwd*'s git metadata (a linked worktree)."""
    try:
        sandbox_git.worktree_layout(cwd)
    except sandbox_git.GitLayoutError:
        return False
    return True


def _deps_note(plan: sandbox_deps.DepsPlan) -> str:
    return _DEPS_NOTE.format(targets=", ".join(m.target for m in plan.mounts))


async def _project_tool_env(
    cwd: Path, packet: ContextPacket | None
) -> tuple[Path | sandbox_deps.DepsPlan | None, str]:
    """The project's cached verifier environment for the task runtime, or why not.

    Python: the same :func:`sandbox.prepare_env` call the verifiers make, with
    the same registry setup command, so the driver and the checks share one
    environment (usually a cache hit), mounted at /venv. Bun: the
    :func:`sandbox_deps.deps_mounts` plan the verifiers use, each mount
    read-only at its workspace's node_modules. On a first attempt the
    manifests are the project's own; on a bounce they are the worktree's as
    attempt 1 left them, which is what the verifiers and the run_tests tool
    already build from, so this adds no new input. A first build takes extra
    wall time before the agent starts; it does not count against the agent's
    in-container time limit. Best-effort: without it the agent still works,
    it just cannot run tests (and says so).
    """
    if not settings.driver_runtime_project_tools:
        return None, "off"
    if settings.verifier_sandbox != "docker":
        return None, "not mounted: verifier sandbox is off"
    ctx = packet.project_context if packet else {}
    toolchain = (ctx.get("sandbox_toolchain") or "python").strip().lower()
    if toolchain not in ("python", "bun"):
        return None, f"not mounted: {toolchain} toolchain"
    try:
        if toolchain == "bun":
            plan = await sandbox_deps.deps_mounts(dict(ctx), Path(cwd))
            if plan is None:
                raise sandbox_deps.DepsUnavailableError("no dependency plan for this project")
            plan = _checked_deps_plan(plan)
            return plan, f"mounted read-only (bun: {len(plan.mounts)} node_modules)"
        venv = await sandbox.prepare_env(
            Path(cwd), ctx.get("sandbox_setup"), allow=ctx.get("sandbox_setup_allow")
        )
    except asyncio.CancelledError:
        raise
    except Exception as exc:  # noqa: BLE001 - a convenience must never fail the dispatch
        logger.warning("claude_code: project environment unavailable for the runtime: %s", exc)
        return None, f"unavailable: {type(exc).__name__}: {str(exc)[:200]}"
    return venv, "mounted read-only"


class _LiveStream:
    """Turns the CLI's stream-json lines into live session events (Stage 4).

    The same steps parse_claude_stream builds after the run, emitted as each
    line arrives so the dashboard's session view shows the agent working.
    """

    def __init__(self, packet: ContextPacket | None) -> None:
        self.tenant = getattr(packet, "tenant_id", None)
        self.task = getattr(packet, "task_id", None)

    def __call__(self, line: str) -> None:
        from life_graph.services.dev import task_events

        try:
            event = json.loads(line)
        except ValueError:
            return
        if not isinstance(event, dict):
            return
        if event.get("type") == "system" and event.get("subtype") == "init":
            model = event.get("model")
            task_events.emit(
                self.tenant, self.task, "agent_start", f"agent started ({model})",
                data={"model": model}, source="agent",
            )  # fmt: skip
            return
        for step in claude_event_steps(event):
            task_events.emit(
                self.tenant,
                self.task,
                step["kind"],
                step.get("content") or "",
                data={k: step[k] for k in ("tool", "is_error", "ref") if step.get(k)},
                source="agent",
            )


class ClaudeCodeDriver:
    """Wraps Claude Code headless mode as an AgentDriver."""

    name = "claude_code"
    max_concurrency = 2
    supports_resume = True

    def __init__(self, binary: str | None = None) -> None:
        self._binary = binary or getattr(settings, "driver_claude_code_bin", "claude")

    @property
    def dispatch_timeout(self) -> int:
        """Read by the dispatcher in place of its 300s fallback."""
        return settings.driver_claude_code_timeout_seconds

    @property
    def billing(self) -> str:
        """``subscription`` on the personal login, ``api`` with an API key."""
        return "api" if settings.driver_claude_code_auth == "api_key" else "subscription"

    # ── Protocol ──────────────────────────────────────────────

    async def available(self) -> bool:
        """Ready when the Claude Code binary is on PATH."""
        found = shutil.which(self._binary) is not None
        if not found:
            logger.debug("claude_code unavailable: %r not on PATH", self._binary)
        return found

    async def resume(
        self,
        packet: ContextPacket,
        workdir: Path,
        session_id: str,
        prompt: str,
        timeout: int = 300,
        *,
        account_id: object = None,
    ) -> DriverResult:
        """Continue session *session_id* with *prompt*: ``claude -p <prompt> --resume <id>``.

        Used by continue_task and run-health rounds (Phase 3b part 2). Host mode only: a task-runtime
        container's config dir is thrown away after each run, so there is no
        session to resume there (refused as ``resume_unsupported``). With
        accounts on, pass the *account_id* the session ran on (its home holds
        the session). The packet's tool scoping applies as in a dispatch.
        """
        if not session_id or not _SESSION_ID.fullmatch(session_id):
            return DriverResult(
                success=False,
                error="claude_code: not a session id",
                metadata={"exit_status": "bad_session"},
            )
        if sandbox.driver_sandbox_enabled():
            return DriverResult(
                success=False,
                error="claude_code: a sandboxed run keeps no session to resume",
                metadata={"exit_status": "resume_unsupported"},
            )
        return await self.dispatch(
            packet, workdir, timeout, _resume=(session_id, prompt), _account_id=account_id
        )

    async def dispatch(
        self,
        packet: ContextPacket,
        workdir: Path,
        timeout: int = 300,
        *,
        _resume: tuple[str, str] | None = None,
        _account_id: object = None,
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
                packet.task_id,
                packet.allowed_tools,
            )
            return DriverResult(
                success=False,
                error=(
                    "No CLI-mappable tools in persona allowlist — refusing to dispatch unscoped"
                ),
                duration_ms=int((time.monotonic() - start) * 1000),
                metadata={"exit_status": "refused_unscoped"},
            )

        prompt = _resume[1].strip() if _resume else self._format_prompt(packet)

        # On the host the CLI's Bash tool would run as this process's user
        # with nothing in between: deny it unless the operator said the host
        # is disposable. In a container it is the container's shell.
        host_shell_denied = not sandbox.driver_sandbox_enabled() and not getattr(
            settings, "driver_allow_host_shell", False
        )
        if host_shell_denied and cli_tools is not None and "Bash" in cli_tools:
            # Loud, not silent: the persona asked for a shell and runs without
            # one, so it cannot run tests or builds itself.
            logger.warning(
                "claude_code task %s: Bash removed from the persona's tools — no driver "
                "sandbox (driver_claude_sandbox=%s); set it to 'task' to give the agent a "
                "contained shell",
                packet.task_id,
                settings.driver_claude_sandbox,
            )
            cli_tools = [t for t in cli_tools if t != "Bash"]
            if not cli_tools:
                return DriverResult(
                    success=False,
                    error=(
                        "This persona needs a shell, and the claude_code driver has no "
                        "sandbox: set driver_claude_sandbox=task (or, on a disposable "
                        "dev box, driver_allow_host_shell=true)"
                    ),
                    duration_ms=int((time.monotonic() - start) * 1000),
                    metadata={"exit_status": "refused_host_shell"},
                )

        # On the host the web tools are denied (_HOST_DENIED_CLI_TOOLS): drop
        # them from the allowlist too, loudly, the same way as Bash above.
        host_mode = not sandbox.driver_sandbox_enabled()
        host_web = [t for t in (cli_tools or []) if t in _HOST_DENIED_CLI_TOOLS]
        if host_mode and host_web:
            logger.warning(
                "claude_code task %s: %s removed from the persona's tools on the host; set "
                "driver_claude_sandbox=task for a run with allowlisted network access",
                packet.task_id,
                ",".join(host_web),
            )
            cli_tools = [t for t in cli_tools or [] if t not in _HOST_DENIED_CLI_TOOLS]
            if not cli_tools:
                return DriverResult(
                    success=False,
                    error=(
                        "This persona needs web access, and the claude_code driver runs "
                        "on the host: set driver_claude_sandbox=task"
                    ),
                    duration_ms=int((time.monotonic() - start) * 1000),
                    metadata={"exit_status": "refused_host_web"},
                )

        lease = await accounts_hook.acquire(
            self.name,
            packet.tenant_id,
            account_id=_account_id or packet.account_id,
            unattended=packet.unattended,
        )
        if lease.refusal is not None:
            lease.refusal.duration_ms = int((time.monotonic() - start) * 1000)
            return lease.refusal
        result = await self._run_cli(
            packet, workdir, timeout, prompt, cli_tools, lease,
            host_mode=host_mode, host_shell_denied=host_shell_denied, start=start,
            resume_id=_resume[0] if _resume else None,
        )  # fmt: skip
        await accounts_hook.release(lease, result)
        return result

    async def _run_cli(
        self,
        packet: ContextPacket,
        workdir: Path,
        timeout: int,
        prompt: str,
        cli_tools: list[str] | None,
        lease: accounts_hook.AccountLease,
        *,
        host_mode: bool,
        host_shell_denied: bool,
        start: float,
        resume_id: str | None,
    ) -> DriverResult:
        """The run itself, once scoping and the account are settled."""
        cwd, worktree = await resolve_workdir(packet, workdir)
        try:
            # stream-json (which -p only allows with --verbose) instead of
            # json: the same final result, plus every step that led to it.
            args = [self._binary, "-p", prompt, "--output-format", "stream-json", "--verbose"]
            if resume_id:
                args += ["--resume", resume_id]
            if lease.model:
                args += ["--model", lease.model]
            args += _permission_args(
                cli_tools, host_mode=host_mode, host_shell_denied=host_shell_denied
            )

            sandboxed = sandbox.driver_sandbox_enabled()
            boundary = settings.driver_claude_sandbox if sandboxed else "host"
            audit: dict = {}
            try:
                returncode, out, err = await self._exec_cli(
                    args, cwd, timeout, packet=packet, audit=audit, lease=lease
                )
            except TimeoutError:
                return DriverResult(
                    success=False,
                    error=f"claude_code timed out after {timeout}s",
                    duration_ms=int((time.monotonic() - start) * 1000),
                    metadata={"exit_status": "timeout", "boundary": boundary, **audit},
                )
            except sandbox.SandboxUnavailableError as exc:
                # Fail closed: sandboxing was asked for and could not run —
                # this must NOT silently degrade onto unsandboxed host
                # execution (see driver_claude_sandbox's docstring).
                return DriverResult(
                    success=False,
                    error=f"claude_code sandbox unavailable: {exc}",
                    duration_ms=int((time.monotonic() - start) * 1000),
                    metadata={"exit_status": "sandbox_unavailable", "boundary": boundary, **audit},
                )

            duration = int((time.monotonic() - start) * 1000)
            stream = (out or b"").decode(errors="replace")
            data, steps = parse_claude_stream(stream)
            success = returncode == 0 and not data.get("is_error", False)
            # Plan windows from rate_limit_event, read passively from the
            # run's own output (Claude's usage endpoint is never polled, U4).
            windows, limit_info = claude_windows(stream)
            extra_md: dict = {"rate_limits": windows} if windows else {}
            if resume_id:
                extra_md["resumed_from"] = resume_id
            if lease.active:
                # The account's kind, not driver_claude_code_auth: an API-key or
                # Vertex account is billed per use, a subscription login is not
                # (risk D4; the dispatcher books only api-billed spend then).
                extra_md["billing"] = lease.billing(self.billing)
            if not success:
                rejected = bool(limit_info) and limit_info.get("status") == "rejected"
                extra_md["failure"] = classify_failure(
                    final_error=str(data.get("result") or ""),
                    stderr=err.decode(errors="replace"),
                    exit_code=returncode,
                    rate_limit_resets=[limit_info["resets_at"]]
                    if rejected and limit_info.get("resets_at")
                    else None,
                    rejected=rejected,
                    login_hint=LOGIN_HINT,
                )
            return DriverResult(
                success=success,
                output=str(data.get("result", ""))[:20000],
                cost_usd=float(data.get("total_cost_usd") or 0.0),
                duration_ms=duration,
                error=None
                if success
                else (
                    str(data.get("result") or err.decode(errors="replace"))[:2000]
                    or f"exit code {returncode}"
                ),
                metadata={
                    "exit_status": "ok" if success else "failed",
                    "session_id": data.get("session_id"),
                    "num_turns": data.get("num_turns"),
                    "model": data.get("model"),
                    "steps": steps,
                    "workdir": str(cwd),
                    "isolated": worktree is not None,
                    "sandboxed": sandboxed,
                    # Which execution boundary this run had: "host" or "task"
                    # (task_runtime). "docker" (fenced) only appears on a refusal.
                    "boundary": boundary,
                    "host_shell": "denied" if host_shell_denied else "allowed",
                    # Host only: whether the file tools were kept to the
                    # working directory (--restricted).
                    **(
                        {"host_files": "workdir_only" if host_shell_denied else "unconfined"}
                        if host_mode
                        else {}
                    ),
                    **extra_md,
                    **audit,
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
        return ["code", "code_change", "test", "review", "refactor", "docs"]

    def cost_per_task(self) -> float:
        """Estimated frontier-class cost per task (actual cost comes back
        in the CLI's JSON output)."""
        return DEFAULT_COST_PER_TASK_USD

    # ── Internals ─────────────────────────────────────────────

    async def _exec_cli(
        self,
        args: list[str],
        cwd: Path,
        timeout: int,
        *,
        packet: ContextPacket | None = None,
        audit: dict | None = None,
        lease: accounts_hook.AccountLease | None = None,
    ) -> tuple[int, bytes, bytes]:
        """Run the CLI invocation, sandboxed or on the host per settings.

        Returns ``(returncode, stdout, stderr)``. With the task runtime,
        *audit* receives its metadata under ``"runtime"`` (image id, network,
        egress allowlist, limits, teardown result), on success and failure.

        Raises:
            TimeoutError: the run did not finish within *timeout*, on
                either path.
            sandbox.SandboxUnavailableError: sandboxing is configured on
                but docker, the image, or the container itself is not
                available, or the fenced "docker" mode is set. Never falls back to the host path — see
                driver_claude_sandbox's comment in config/drivers.py.
        """
        account = lease if lease is not None and lease.active else None
        # An account brings its own login (home) or key; the configured
        # driver_claude_code_auth applies only when no account is in use.
        api_key = None if account else _api_key()
        if not sandbox.driver_sandbox_enabled():
            env = host_driver_env({"ANTHROPIC_API_KEY": api_key} if api_key else None)
            if account:
                env = account.apply(env)
            # Allowlisted environment, never the API process's own (database
            # URL, provider keys, LIFE_GRAPH_*); own session so a timeout can
            # kill whatever the CLI started, not just the CLI.
            proc = await asyncio.create_subprocess_exec(
                *args,
                cwd=str(cwd),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                start_new_session=True,
                limit=STREAM_LIMIT,
            )
            try:
                out, err = await communicate_streaming(proc, timeout, _LiveStream(packet))
            except TimeoutError:
                await kill_process_group(proc)
                with contextlib.suppress(Exception):
                    await proc.communicate()
                raise
            except (asyncio.CancelledError, Exception):
                # A cancel (dev-task runner), or reading its output failed: stop
                # the CLI and whatever it started -- never leave it running
                # unattended -- and reap it.
                await kill_process_group(proc)
                with contextlib.suppress(Exception):
                    await asyncio.wait_for(proc.wait(), 5)
                raise
            return proc.returncode, out, err

        # The old open-network "docker" mode is fenced (D25): refuse before
        # any login is staged or container started.
        sandbox.refuse_legacy_driver_sandbox()

        if account:
            # The task runtime gets secrets by name and a throwaway config
            # dir: an API-key account works; a login home cannot be mounted
            # (a refresh inside would revoke it, as with the staged copy).
            if account.kind != "api_key":
                raise sandbox.SandboxUnavailableError(
                    f"claude_code account {account.name!r} ({account.kind}) runs on the host "
                    "only; the task runtime takes an api_key account or the configured token"
                )
            api_key = account.env.overlay.get("ANTHROPIC_API_KEY")

        # API-key mode stages no personal credentials at all. OAuth mode uses
        # the long-lived token (nothing copied, nothing refreshed); copying
        # the host's login file is a legacy opt-in, since a refresh inside
        # the container revokes the host's copy.
        creds_dir = None
        oauth_token = None
        if not api_key:
            oauth_token = _oauth_token()
            if not oauth_token:
                if not settings.driver_claude_code_allow_staged_login:
                    raise sandbox.SandboxUnavailableError(_NO_SANDBOX_LOGIN)
                creds_source = Path(settings.driver_claude_code_creds_path).expanduser()
                creds_dir = await sandbox.stage_credentials(creds_source)
        if audit is not None:
            # Which login the container got (never the value).
            audit["login"] = (
                "api_key" if api_key else "oauth_token" if oauth_token else "staged_copy"
            )
        try:
            result = await self._run_in_task_runtime(
                args, cwd, creds_dir, timeout=timeout, api_key=api_key, packet=packet,
                audit=audit, oauth_token=oauth_token,
            )  # fmt: skip
        except sandbox.SandboxUnavailableError as exc:
            if "timed out" in str(exc):
                raise TimeoutError(str(exc)) from exc
            raise
        finally:
            if creds_dir is not None:
                shutil.rmtree(creds_dir, ignore_errors=True)
        return result.returncode, result.stdout.encode(), result.stderr.encode()

    @staticmethod
    async def _run_in_task_runtime(
        args: list[str],
        cwd: Path,
        creds_dir: Path | None,
        *,
        timeout: int,
        api_key: str | None,
        packet: ContextPacket | None,
        audit: dict | None,
        oauth_token: str | None = None,
    ) -> sandbox.SandboxResult:
        """The claude_code CLI in its per-task runtime (services/dev/task_runtime.py)."""
        from life_graph.services.dev import task_runtime

        # Both secrets go by NAME (docker reads the value from its own
        # environment), with a throwaway config dir on the container's tmpfs.
        if api_key:
            secret_env = {"ANTHROPIC_API_KEY": api_key}
        elif oauth_token:
            secret_env = {"CLAUDE_CODE_OAUTH_TOKEN": oauth_token}
        else:
            secret_env = {}

        env = {
            # Nothing but the API and the token refresh: no telemetry, no
            # update checks, no error reporting — the allowlist would refuse
            # them anyway, and each refusal is a slow retry.
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
            "DISABLE_AUTOUPDATER": "1",
            # An agent that runs Python in its shell otherwise leaves
            # __pycache__/*.pyc in the worktree, and so in the landed diff
            # (seen in the first end-to-end run, 2026-11-18).
            "PYTHONDONTWRITEBYTECODE": "1",
            "CLAUDE_CONFIG_DIR": "/tmp/.claude" if secret_env else "/claude-config",
            # The image carries pytest/ruff/mypy (docker/claude-driver): their
            # caches go to /tmp, never into the worktree (the landed diff).
            **_TOOL_CACHE_ENV,
        }
        tool_env, tool_note = await _project_tool_env(cwd, packet)
        venv = tool_env if isinstance(tool_env, Path) else None
        deps = tool_env if isinstance(tool_env, sandbox_deps.DepsPlan) else None
        # The image's own binary, not args[0] (the host's configured path).
        command: tuple[str, ...] = (sandbox.DRIVER_CLI, *args[1:])
        if venv is not None:
            env.update(_PROJECT_ENV_VARS)
        notes: list[str] = []
        if deps is not None:
            env.update(_deps_env(deps))
            notes.append(_deps_note(deps))
        if _git_mountable(cwd):
            notes.append(GIT_NOTE)
        if notes:
            command = (*command, "--append-system-prompt", "\n\n".join(notes))
        if audit is not None:
            audit["tool_env"] = tool_note
        req = task_runtime.RuntimeRequest(
            task_id=str(packet.task_id) if packet else "unknown",
            tenant_id=str(packet.tenant_id) if packet else "unknown",
            driver="claude_code",
            image=settings.driver_claude_sandbox_image,
            command=command,
            workspace=cwd,
            credentials=None if secret_env else creds_dir,
            tool_env=venv,
            read_only_binds=tuple((m.source, m.target) for m in deps.mounts) if deps else (),
            env=env,
            secret_env=secret_env,
            egress_allowlist=tuple(settings.driver_runtime_egress_allowlist_list),
            memory=settings.driver_claude_sandbox_memory,
            cpus=settings.driver_claude_sandbox_cpus,
            pids_limit=settings.driver_runtime_pids_limit,
            timeout=timeout,
            on_stdout_line=_LiveStream(packet),
        )
        try:
            outcome = await task_runtime.runtime.run(req)
        except sandbox.SandboxUnavailableError as exc:
            if audit is not None and getattr(exc, "runtime_metadata", None):
                audit["runtime"] = exc.runtime_metadata
            raise
        if audit is not None:
            audit["runtime"] = outcome.metadata
        return sandbox.SandboxResult(outcome.returncode, outcome.stdout, outcome.stderr)

    @staticmethod
    def _format_prompt(packet: ContextPacket) -> str:
        """Render the context packet as a headless prompt.

        Personal data (CHARTER invariant 7): Claude runs on a cloud model, so
        memories, preferences and procedures are never in the prompt,
        whatever ``packet.private`` says — the same rule as the codex and
        gemini drivers (``cli_driver.build_prompt``). Before 2026-11-28 a
        non-private packet carried all three. What leaves the machine is the
        persona's system prompt (when the dispatch was pinned to one), the
        task and the project metadata; the code is read from the worktree.
        """
        parts = []
        if packet.persona_system_prompt:
            parts.append(packet.persona_system_prompt)
        parts.append(packet.instruction)
        if packet.project_context:
            safe_project = {
                k: v for k, v in packet.project_context.items() if k not in ("path", "isolation")
            }
            if safe_project:
                parts.append(f"\n## Project context\n{json.dumps(safe_project, default=str)}")
        return "\n".join(parts)

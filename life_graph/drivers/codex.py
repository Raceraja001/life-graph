"""OpenAI Codex CLI as a dev-task engine: ``codex exec --json`` on the host.

One headless process per dispatch, prompt on stdin, JSON lines on stdout,
in the task's worktree (drivers/cli_driver.py has the common flow). Flags
verified against ``codex exec --help`` of codex-cli 0.172.0 (2026-11-27), and
every ``-c`` override below was checked to load with that version's config
validation (``codex -c ... features list``, which errors on a bad value):

    codex exec --json --color never --ignore-user-config
               -s read-only|workspace-write
               -c approval_policy="never"
               -c sandbox_workspace_write.network_access=false
               -c web_search="disabled"
               -c features.<browser_use|computer_use|in_app_browser|apps|plugins|
                           image_generation|hooks|memories|goals>=false
               [--skip-git-repo-check]  (only for a scratch dir, never a project)
               [-m <driver_codex_model>]
               -

- **Sandbox from the task mode.** A plan (or a persona with no write tool)
  runs ``read-only``; everything else ``workspace-write``. ``exec`` cannot ask
  for approval, so the policy is "never": a command outside the sandbox fails
  rather than prompting. Never passed: ``--dangerously-bypass-approvals-and-
  sandbox``, ``--add-dir``, ``--cd``, ``--worktree``, ``--remote``, ``--trust``.
- **Nothing from the user's config.** ``--ignore-user-config`` keeps the
  owner's ``~/.codex/config.toml`` (its MCP servers, plugins, profiles) out of
  an unattended run; auth still comes from ``CODEX_HOME``. Features that reach
  the network or the desktop are switched off with ``-c features.X=false``,
  not ``--disable X``: the latter fails the run on a feature name a later
  version drops.
- **Host shell.** Codex cannot run without its shell, and its sandbox limits
  writes and network but not reads, so on the host it could read anything
  this user can and send it to the model. It therefore runs only when
  ``driver_allow_host_shell`` says the host is a disposable dev box; otherwise
  the dispatch is refused. The task container runtime is Phase 3b.

Event stream (``exec --json``): ``thread.started {thread_id}``,
``turn.started``, ``item.started|updated|completed {item}``, ``turn.completed
{usage}``, ``turn.failed {error}``, ``error {message}``; rate-limit snapshots
arrive as ``token_count`` records (bare, under ``msg``, or as an ``event_msg``
payload). Item types: agent_message, reasoning, command_execution,
file_change, mcp_tool_call, web_search, todo_list, error. Mapping rebuilt from
race-app ``agents/runtimes/codex-parser.ts`` / ``codex-items.ts``.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from life_graph.config import settings
from life_graph.drivers.base import DriverResult
from life_graph.drivers.cli_driver import EventParser, SubscriptionCliDriver
from life_graph.drivers.cli_failure import normalize_reset
from life_graph.drivers.cli_run import exit_code_login_check

if TYPE_CHECKING:
    from pathlib import Path

    from life_graph.drivers.base import ContextPacket

LOGIN_HINT = "run `codex login`"

# Features off for an unattended run: each reaches the network, the desktop
# or state outside the worktree. Checked to exist in codex-cli 0.172.0.
DISABLED_FEATURES = (
    "browser_use",
    "computer_use",
    "in_app_browser",
    "apps",
    "plugins",
    "image_generation",
    "hooks",
    "memories",
    "goals",
)

MAX_TOOL_OUTPUT_CHARS = 16_000


def codex_argv(
    binary: str, *, read_only: bool, model: str = "", in_git_repo: bool = True
) -> list[str]:
    """The ``codex exec`` command line for one run (the prompt goes on stdin)."""
    argv = [binary, "exec", "--json", "--color", "never", "--ignore-user-config"]
    argv += ["-s", "read-only" if read_only else "workspace-write"]
    argv += ["-c", 'approval_policy="never"']
    argv += ["-c", "sandbox_workspace_write.network_access=false"]
    argv += ["-c", 'web_search="disabled"']
    for feature in DISABLED_FEATURES:
        argv += ["-c", f"features.{feature}=false"]
    if not in_git_repo:
        # The dispatcher's scratch dir (no project): Codex refuses a non-git
        # directory otherwise. A project worktree always has .git.
        argv.append("--skip-git-repo-check")
    if model:
        argv += ["-m", model]
    argv.append("-")
    return argv


def rate_limit_snapshot(raw: object) -> tuple[list[dict], bool, list[str]] | None:
    """A Codex ``rate_limits`` snapshot -> (windows, rejected, reset times).

    Accepts both spellings Codex uses (snake_case in exec/rollout records,
    camelCase over app-server). A window at 100% or a
    ``rate_limit_reached_type`` means the limit was hit; the resets returned
    are those of the windows at 100%, else of every window. None when the
    snapshot has no usable window.
    """
    if not isinstance(raw, dict):
        return None

    def pick(rec: dict, *keys: str) -> object:
        return next((rec[k] for k in keys if rec.get(k) is not None), None)

    windows: list[dict] = []
    for slot in ("primary", "secondary"):
        rec = raw.get(slot)
        if not isinstance(rec, dict):
            continue
        used = pick(rec, "used_percent", "usedPercent")
        if not isinstance(used, (int, float)) or isinstance(used, bool):
            continue
        minutes = pick(rec, "window_minutes", "windowDurationMins", "window_duration_mins")
        window = {
            "slot": slot,
            "used_percent": float(used),
            "window_minutes": minutes if isinstance(minutes, int) else None,
            "resets_at": normalize_reset(pick(rec, "resets_at", "resetsAt")),
        }
        windows.append(window)
    reached = pick(raw, "rate_limit_reached_type", "rateLimitReachedType")
    if not windows and not reached:
        return None
    full = [w for w in windows if w["used_percent"] >= 100]
    rejected = bool(reached) or bool(full)
    resets = sorted(w["resets_at"] for w in (full or windows) if w["resets_at"])
    return windows, rejected, resets


def _token_count(event: dict) -> dict | None:
    """The ``token_count`` record in any of its three envelopes, else None."""
    if event.get("type") == "token_count":
        return event
    msg = event.get("msg")
    if isinstance(msg, dict) and msg.get("type") == "token_count":
        return msg
    payload = event.get("payload")
    is_payload = isinstance(payload, dict) and payload.get("type") == "token_count"
    return payload if event.get("type") == "event_msg" and is_payload else None


def _mcp_result_text(item: dict) -> str:
    error = item.get("error")
    if isinstance(error, dict) and error.get("message"):
        return str(error["message"])
    result = item.get("result")
    content = result.get("content") if isinstance(result, dict) else None
    if isinstance(content, list):
        return "\n".join(
            str(b.get("text", "")) if b.get("type") == "text" else f"[{b.get('type')}]"
            for b in content
            if isinstance(b, dict)
        )
    return "" if result is None else json.dumps(result, default=str)


def _tool_view(item: dict) -> tuple[str, str, str, bool] | None:
    """(tool name, input JSON, output, failed) for a tool-like item, else None."""
    status = item.get("status")
    failed = status in ("failed", "declined")
    itype = item.get("type")
    if itype == "command_execution":
        code = item.get("exit_code")
        output = str(
            item.get("aggregated_output") or ("(declined)" if status == "declined" else "")
        )
        failed = failed or (isinstance(code, int) and code != 0)
        return "shell", json.dumps({"command": item.get("command")}), output, failed
    if itype == "file_change":
        changes = [c for c in item.get("changes") or [] if isinstance(c, dict)]
        summary = [{"path": c.get("path"), "kind": c.get("kind") or "update"} for c in changes]
        output = "patch failed" if failed else f"{len(changes)} file(s) changed"
        return "apply_patch", json.dumps({"changes": summary}), output, failed
    if itype == "mcp_tool_call":
        server, tool = item.get("server") or "", item.get("tool") or "tool"
        error = item.get("error")
        failed = failed or (isinstance(error, dict) and bool(error.get("message")))
        name = f"{server}.{tool}" if server else str(tool)
        return name, json.dumps(item.get("arguments"), default=str), _mcp_result_text(item), failed
    if itype == "web_search":
        return "web_search", json.dumps({"query": item.get("query")}), "", failed
    return None


class CodexEventParser(EventParser):
    """``codex exec --json`` lines -> steps, summary text, thread id, usage, limits."""

    def __init__(self) -> None:
        super().__init__()
        self._open_calls: set[str] = set()
        self._last_todo = ""

    def on_event(self, event: dict) -> list[dict]:
        run = self.run
        tc = _token_count(event)
        if tc is not None:
            self._limits(tc.get("rate_limits") or tc.get("rateLimits"))
            return []
        etype = event.get("type")
        if etype == "thread.started":
            run.session_id = event.get("thread_id") or run.session_id
            return []
        if etype in ("item.started", "item.updated", "item.completed"):
            item = event.get("item")
            if isinstance(item, dict):
                return self._item(etype.split(".", 1)[1], item)
            return []
        if etype == "turn.completed":
            run.turns += 1
            run.completed = True
            usage = event.get("usage") or {}
            if isinstance(usage, dict):
                run.add_usage(
                    input_tokens=usage.get("input_tokens"),
                    cached_input_tokens=usage.get("cached_input_tokens"),
                    output_tokens=usage.get("output_tokens"),
                )
            self._limits(event.get("rate_limits"))
            return []
        if etype == "turn.failed":
            run.completed = False
            error = event.get("error")
            message = str((error or {}).get("message") or "") if isinstance(error, dict) else ""
            run.final_error = message.strip() or (run.warnings[-1] if run.warnings else "")
            run.final_error = run.final_error or "codex turn failed"
            return [{"kind": "error", "content": run.final_error, "at": None}]
        if etype == "error":
            message = str(event.get("message") or "").strip()
            if not message:
                return []
            run.warnings.append(message)
            return [{"kind": "error", "content": message, "at": None}]
        return []

    def _limits(self, raw: object) -> None:
        snap = rate_limit_snapshot(raw)
        if snap is None:
            return
        windows, rejected, resets = snap
        self.run.rate_limits = windows
        if rejected:
            self.run.rate_limit_rejected = True
            self.run.rate_limit_resets = resets

    def _item(self, phase: str, item: dict) -> list[dict]:
        itype = item.get("type")
        ref = item.get("id") or None
        if itype == "agent_message":
            text = str(item.get("text") or "").strip()
            if phase != "completed" or not text:
                return []
            self.run.texts.append(text)
            return [{"kind": "text", "content": text, "at": None}]
        if itype == "reasoning":
            text = str(item.get("text") or "").strip()
            if phase != "completed" or not text:
                return []
            return [{"kind": "thinking", "content": text, "at": None}]
        if itype == "todo_list":
            lines = [
                f"[{'x' if t.get('completed') is True else ' '}] {t.get('text')}"
                for t in item.get("items") or []
                if isinstance(t, dict) and str(t.get("text") or "").strip()
            ]
            text = "Plan:\n" + "\n".join(lines) if lines else ""
            if not text or text == self._last_todo:
                return []
            self._last_todo = text
            return [{"kind": "thinking", "content": text, "at": None}]
        if itype == "error":
            message = str(item.get("message") or "").strip()
            if phase != "completed" or not message:
                return []
            self.run.warnings.append(message)
            return [{"kind": "error", "content": message, "at": None}]
        view = _tool_view(item)
        if view is None:
            return []
        tool, content, output, failed = view
        call = {"kind": "tool_call", "tool": tool, "content": content, "ref": ref, "at": None}
        if phase == "started":
            if ref:
                self._open_calls.add(ref)
            return [call]
        if phase != "completed":
            return []
        opened = bool(ref) and ref in self._open_calls
        self._open_calls.discard(ref or "")
        result: dict = {
            "kind": "tool_result",
            "tool": tool,
            "content": output[:MAX_TOOL_OUTPUT_CHARS],
            "ref": ref,
            "at": None,
        }
        if failed:
            result["is_error"] = True
        return [result] if opened else [call, result]


class CodexDriver(SubscriptionCliDriver):
    """Codex ``exec`` mode, as an AgentDriver."""

    name = "codex"
    login_hint = LOGIN_HINT

    @property
    def enabled(self) -> bool:
        return settings.driver_codex_enabled

    @property
    def binary(self) -> str:
        return self._binary_override or settings.driver_codex_bin

    @property
    def model(self) -> str:
        return settings.driver_codex_model

    @property
    def dispatch_timeout(self) -> int:
        return settings.driver_codex_timeout_seconds

    def env_extra(self) -> dict[str, str]:
        # Where Codex keeps its login: a location, not a credential.
        home = os.environ.get("CODEX_HOME")
        return {"CODEX_HOME": home} if home else {}

    async def login_check(self, path: str, env: dict[str, str]) -> bool | None:
        # Exit code only: `codex login status` prints how it is signed in,
        # and with an API key that line names the key.
        return await exit_code_login_check(["login", "status"], path, env)

    def refusal(self, packet: ContextPacket) -> DriverResult | None:
        if settings.driver_allow_host_shell:
            return None
        return DriverResult(
            success=False,
            error=(
                "The codex driver runs on the host, and Codex always has a shell that can "
                "read any file this user can: set driver_allow_host_shell=true on a "
                "disposable dev box (a container runtime for codex is not built yet)"
            ),
            metadata={"exit_status": "refused_host_shell", "driver": self.name},
        )

    def build_argv(
        self, binary: str, cwd: Path, *, read_only: bool, scratch: Path
    ) -> tuple[list[str], dict[str, str]]:
        argv = codex_argv(
            binary, read_only=read_only, model=self.model, in_git_repo=(cwd / ".git").exists()
        )
        return argv, {}

    def new_parser(self) -> CodexEventParser:
        return CodexEventParser()

    def run_metadata(self, *, read_only: bool) -> dict:
        return {
            "sandbox": "read-only" if read_only else "workspace-write",
            "host_shell": "codex_sandbox",
            # Codex's sandbox confines writes and network, not reads.
            "host_files": "read_unconfined",
        }

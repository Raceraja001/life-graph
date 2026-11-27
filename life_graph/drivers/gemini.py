"""Google's Gemini CLI as a dev-task engine: ``gemini -p … -o stream-json``.

Headless mode with streamed JSON events, in the task's worktree, prompt on
stdin (``-p`` text is appended to stdin, so ``-p`` carries only a closing
line). Flags verified against ``gemini --help`` of 0.71.1 (2026-11-27); the
behaviour notes below were read from that version's bundle, not exercised in
a signed-in run:

    gemini -o stream-json --approval-mode plan|auto_edit
           --allowed-mcp-server-names __life_graph_none__
           [-m <driver_gemini_model>] -p "<closing line>"
    env:   GEMINI_CLI_SYSTEM_SETTINGS_PATH=<run-scoped settings file>

- **Approval mode from the task mode.** A plan (or a persona with no write
  tool) runs ``plan`` (read-only); everything else ``auto_edit`` (edits are
  auto-approved, anything else needs an approval nobody is there to give).
  Never passed: ``--yolo`` / ``--approval-mode yolo``, ``-w`` (the dispatcher
  owns the worktree), ``--skip-trust``, ``--include-directories``.
- **Run-scoped system settings.** ``GEMINI_CLI_SYSTEM_SETTINGS_PATH`` points
  at a file written for this run; system settings take precedence over user
  and workspace settings, so a ``.gemini/settings.json`` inside the worktree
  cannot turn things back on. It excludes the shell and web tools, disables
  hooks, blanks the tool discovery/call commands (both run a shell command),
  and turns usage statistics and telemetry off. Excluded tools are merged as
  a set with any other settings layer.
- **No MCP servers.** ``--allowed-mcp-server-names`` with a name no server has:
  with an allowlist, every server not on it is blocked.
- **Files.** The CLI's own file tools check paths against the workspace
  directories (the worktree); no ``--include-directories`` is passed.
- **Folder trust.** If the owner has turned on Gemini's folder trust, a
  headless run in an untrusted worktree stops with an error naming
  ``--skip-trust``. It is deliberately not passed: trusting the worktree would
  load settings an earlier agent attempt may have written there.

Event stream (``JsonStreamEventType`` in 0.71.1): ``init {session_id, model}``,
``message {role, content, delta}``, ``tool_use {tool_name, tool_id,
parameters}``, ``tool_result {tool_id, status, output, error}``, ``error
{severity, message}``, ``result {status, error?, stats}`` with
``stats.{total_tokens, input_tokens, output_tokens, cached, duration_ms}``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from life_graph.config import settings
from life_graph.drivers.cli_driver import EventParser, SubscriptionCliDriver

LOGIN_HINT = "run `gemini` once and choose Login with Google"

# Matches no configured server, so the allowlist blocks them all.
NO_MCP_SERVER = "__life_graph_none__"

# Tool names in gemini-cli 0.71.1 (SHELL_TOOL_NAME, WEB_FETCH_TOOL_NAME,
# WEB_SEARCH_TOOL_NAME).
EXCLUDED_TOOLS = ("run_shell_command", "web_fetch", "google_web_search")

PROMPT_TAIL = "Do the task described above."

# A key or cloud credential the CLI can use instead of the Google login;
# names only, the values are never read here.
_KEY_VARIABLES = (
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "GOOGLE_GENAI_USE_VERTEXAI",
    "GOOGLE_APPLICATION_CREDENTIALS",
)

MAX_TOOL_OUTPUT_CHARS = 16_000


def system_settings() -> dict:
    """The run-scoped system settings file's content."""
    return {
        "tools": {"exclude": list(EXCLUDED_TOOLS), "discoveryCommand": "", "callCommand": ""},
        "hooksConfig": {"enabled": False},
        "privacy": {"usageStatisticsEnabled": False},
        "telemetry": {"enabled": False},
    }


def gemini_argv(
    binary: str, *, read_only: bool, model: str = "", resume: str | None = None
) -> list[str]:
    """The headless ``gemini`` command line for one run (the prompt goes on stdin).

    *resume*: ``--resume <session uuid>`` (0.71.1 accepts ``latest``, an index
    or a UUID; only a UUID is passed). Sessions are kept per project
    directory under the CLI home, so a resume must run in the same workdir
    and the same ``GEMINI_CLI_HOME`` as the session it continues.
    """
    argv = [binary, "-o", "stream-json"]
    if resume:
        argv += ["--resume", resume]
    argv += ["--approval-mode", "plan" if read_only else "auto_edit"]
    argv += ["--allowed-mcp-server-names", NO_MCP_SERVER]
    if model:
        argv += ["-m", model]
    argv += ["-p", PROMPT_TAIL]
    return argv


class GeminiEventParser(EventParser):
    """``gemini -o stream-json`` lines -> steps, text, session id, usage."""

    def __init__(self) -> None:
        super().__init__()
        self._text: list[str] = []
        self._text_at: str | None = None

    def _flush(self) -> list[dict]:
        text = "".join(self._text).strip()
        self._text = []
        if not text:
            return []
        self.run.texts.append(text)
        return [{"kind": "text", "content": text, "at": self._text_at}]

    def on_event(self, event: dict) -> list[dict]:
        run = self.run
        etype = event.get("type")
        at = event.get("timestamp") if isinstance(event.get("timestamp"), str) else None
        if etype == "init":
            run.session_id = event.get("session_id") or run.session_id
            run.model = event.get("model") or run.model
            return []
        if etype == "message":
            if event.get("role") != "assistant":
                return []
            content = event.get("content")
            if isinstance(content, str) and content:
                if not self._text:
                    self._text_at = at
                self._text.append(content)
                if not event.get("delta"):
                    return self._flush()
            return []
        steps = self._flush()
        if etype == "tool_use":
            run.turns += 1
            steps.append(
                {
                    "kind": "tool_call",
                    "tool": event.get("tool_name"),
                    "content": json.dumps(event.get("parameters"), default=str),
                    "ref": event.get("tool_id"),
                    "at": at,
                }
            )
        elif etype == "tool_result":
            failed = event.get("status") == "error"
            error = event.get("error") if isinstance(event.get("error"), dict) else {}
            output = (
                str(error.get("message") or event.get("output") or "")
                if failed
                else str(event.get("output") or "")
            )
            step = {
                "kind": "tool_result",
                "content": output[:MAX_TOOL_OUTPUT_CHARS],
                "ref": event.get("tool_id"),
                "at": at,
            }
            if failed:
                step["is_error"] = True
            steps.append(step)
        elif etype == "error":
            message = str(event.get("message") or "").strip()
            if message:
                run.warnings.append(message)
                steps.append({"kind": "error", "content": message, "at": at})
        elif etype == "result":
            stats = event.get("stats") if isinstance(event.get("stats"), dict) else {}
            run.add_usage(
                input_tokens=stats.get("input_tokens"),
                cached_input_tokens=stats.get("cached"),
                output_tokens=stats.get("output_tokens"),
                total_tokens=stats.get("total_tokens"),
            )
            if event.get("status") == "success":
                run.completed = True
            else:
                run.completed = False
                error = event.get("error") if isinstance(event.get("error"), dict) else {}
                run.final_error = str(error.get("message") or "").strip() or (
                    run.warnings[-1] if run.warnings else "gemini run failed"
                )
                steps.append({"kind": "error", "content": run.final_error, "at": at})
        return steps

    def finish(self) -> list[dict]:
        """Text still being streamed when the run ended (killed mid-message)."""
        steps = self._flush()
        self.run.steps.extend(steps)
        return steps


class GeminiDriver(SubscriptionCliDriver):
    """Gemini CLI headless mode, as an AgentDriver."""

    name = "gemini"
    login_hint = LOGIN_HINT

    @property
    def enabled(self) -> bool:
        return settings.driver_gemini_enabled

    @property
    def binary(self) -> str:
        return self._binary_override or settings.driver_gemini_bin

    @property
    def model(self) -> str:
        return settings.driver_gemini_model

    @property
    def dispatch_timeout(self) -> int:
        return settings.driver_gemini_timeout_seconds

    async def login_check(self, path: str, env: dict[str, str]) -> bool | None:
        """Signed in when the Google login file exists or a key variable is passed.

        Existence only; the file is never opened.
        """
        # GEMINI_CLI_HOME (an account's home) replaces the directory .gemini/
        # lives under (homedir() in gemini-cli 0.71.1).
        home = Path(env.get("GEMINI_CLI_HOME") or env.get("HOME") or Path.home())
        if (home / ".gemini" / "oauth_creds.json").is_file():
            return True
        return any(env.get(name) for name in _KEY_VARIABLES)

    def build_argv(
        self,
        binary: str,
        cwd: Path,
        *,
        read_only: bool,
        scratch: Path,
        model: str = "",
        resume: str | None = None,
    ) -> tuple[list[str], dict[str, str]]:
        settings_file = scratch / "system-settings.json"
        settings_file.write_text(json.dumps(system_settings()))
        os.chmod(settings_file, 0o600)
        env = {"GEMINI_CLI_SYSTEM_SETTINGS_PATH": str(settings_file)}
        return gemini_argv(binary, read_only=read_only, model=model, resume=resume), env

    def new_parser(self) -> GeminiEventParser:
        return GeminiEventParser()

    def run_metadata(self, *, read_only: bool) -> dict:
        return {
            "approval_mode": "plan" if read_only else "auto_edit",
            "host_shell": "excluded",
            "host_files": "workspace_only",
        }

"""Claude Code lifecycle-hook entrypoint.

Run as ``python3 -m life_graph.integrations.claude_code.hook``. Claude Code
pipes one JSON object on stdin and reads stdout for an optional response.

Hook-contract notes (verified against the zod input schemas embedded in the
Claude Code 2.1.241 binary — see ``docs/integrations/claude-code.md``):

* Common fields on every event: ``session_id``, ``transcript_path``, ``cwd``,
  and the optionals ``prompt_id``, ``permission_mode``, ``agent_id``,
  ``agent_type``, ``effort``.
* ``SessionStart`` carries ``source`` (``startup|resume|clear|compact|fork``),
  **not** ``session_start_mode``.
* ``SessionEnd`` carries ``reason``, **not** ``session_end_mode``.
* ``UserPromptSubmit`` carries ``prompt``, **not** ``user_prompt``.
* ``PostToolUse`` carries ``tool_name``, ``tool_input``, ``tool_response``
  (**not** ``tool_result``), ``tool_use_id`` and ``duration_ms``.
* Tool *failures* arrive as a separate ``PostToolUseFailure`` event carrying
  ``error``; ``PostToolUse`` does not fire for them.
* Output is a top-level object; ``additionalContext`` nests inside
  ``hookSpecificOutput`` (with ``hookEventName``), while ``systemMessage`` is
  top-level.

Failure posture: every path is wrapped and the process always exits 0. Exit 2
would *block* the developer's action and is never used. Nothing but deliberate
hook JSON is ever written to stdout.
"""

from __future__ import annotations

import json
import sys
from typing import Any

from life_graph.integrations.claude_code.config import (
    SURFACE_ASSISTANT_MESSAGE,
    SURFACE_CLI,
    SURFACE_TOOL_EXHAUST,
    HookConfig,
    in_project_roots,
    load_config,
    normalize_path,
)

#: Assistant messages shorter than this ("Done.", "Fixed it.") are noise.
MIN_ASSISTANT_MESSAGE_CHARS = 40

#: Envelopes Claude Code injects into the prompt stream that are not the
#: developer typing. A task notification arrives as a user turn, so without
#: this the spine learned facts like "The task with ID 'blwug1frp' has been
#: completed" — and one of those per background task.
MACHINE_PROMPT_TAGS = (
    "<task-notification>",
    "<local-command-stdout>",
    "<command-name>",
    "<command-message>",
)


def is_machine_prompt(prompt: str) -> bool:
    """True when a UserPromptSubmit turn was injected, not typed.

    Matched at the start of the prompt only: the developer quoting one of
    these tags mid-sentence is still the developer speaking.
    """
    return prompt.lstrip().startswith(MACHINE_PROMPT_TAGS)


#: Upper bound on the SessionEnd spool flush, so quitting never hangs.
FLUSH_BUDGET_SECONDS = 3.0


# ── Payload helpers ──────────────────────────────────────────────────────


def _base_properties(payload: dict[str, Any]) -> dict[str, Any]:
    """Provenance every capture from this integration carries."""
    props = {
        "integration": "claude_code",
        "hook_event": payload.get("hook_event_name"),
        "session_id": payload.get("session_id"),
        "cwd": payload.get("cwd"),
    }
    for optional in ("prompt_id", "permission_mode", "agent_id", "agent_type"):
        value = payload.get(optional)
        if value:
            props[optional] = value
    from life_graph.integrations.claude_code.context import project_name

    cwd = payload.get("cwd")
    if cwd:
        props["project"] = project_name(cwd)
    return props


def _capture(
    payload: dict[str, Any],
    cfg: HookConfig,
    *,
    surface: str,
    content: str,
    properties: dict[str, Any] | None = None,
    client=None,
) -> None:
    """Build, send and (on transient failure) spool one capture event."""
    from life_graph.integrations.claude_code.transport import build_capture_payload, deliver

    props = _base_properties(payload)
    props.update(properties or {})
    body = build_capture_payload(surface=surface, content=content, cfg=cfg, properties=props)
    result = deliver(body, cfg, client=client)
    _log(cfg, "capture", surface=surface, status=str(result.status), detail=result.detail)


def _log(cfg: HookConfig, message: str, **fields: Any) -> None:
    from life_graph.integrations.claude_code.transport import log_debug

    log_debug(cfg, message, **fields)


# ── Handlers ─────────────────────────────────────────────────────────────


def handle_session_start(
    payload: dict[str, Any], cfg: HookConfig, *, client=None
) -> dict[str, Any] | None:
    """Inject proactive recall as ``additionalContext``. The payoff event.

    Skipped for ``source == "compact"``: that fires when context is being
    *compacted*, not started, and re-injecting recall there would fight the
    compaction it was triggered by.
    """
    if payload.get("source") == "compact":
        return None

    from life_graph.integrations.claude_code.context import build_session_context
    from life_graph.integrations.claude_code.render import render_recall, summarize_counts
    from life_graph.integrations.claude_code.transport import post_recall

    context = build_session_context(payload)
    recall = post_recall(context, cfg, client=client)
    markdown = render_recall(recall)
    _log(cfg, "session_start", context=context, chars=len(markdown))
    if not markdown:
        return None

    output: dict[str, Any] = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": markdown,
        }
    }
    note = summarize_counts(recall)
    if note:
        output["systemMessage"] = note
    return output


def handle_user_prompt_submit(
    payload: dict[str, Any], cfg: HookConfig, *, client=None
) -> dict[str, Any] | None:
    """Capture what the developer typed.

    Surface ``cli`` — TrustTier.SELF, the developer's own words. Returns no
    output at all: ``updatedPrompt`` is deliberately never set, because
    rewriting the developer's prompt is not this integration's business.
    """
    prompt = (payload.get("prompt") or "").strip()
    if not prompt or is_machine_prompt(prompt):
        return None
    _capture(payload, cfg, surface=SURFACE_CLI, content=prompt, client=client)
    return None


def _tool_exit_status(payload: dict[str, Any]) -> str:
    """Derive ``ok``/``error`` from the tool response.

    ``PostToolUse`` only fires for successful calls in current Claude Code, but
    the response is inspected anyway so a future shape change degrades to a
    correct high-signal classification rather than a silent misclassification.
    """
    response = payload.get("tool_response")
    if isinstance(response, dict):
        if response.get("is_error") or response.get("error"):
            return "error"
        if response.get("success") is False:
            return "error"
    return "ok"


def handle_post_tool_use(
    payload: dict[str, Any], cfg: HookConfig, *, client=None, rng=None
) -> dict[str, Any] | None:
    """Capture sampled tool exhaust — surface ``tool_exhaust`` (VERIFIED).

    The sampling decision happens *before* any HTTP call, so a throttled tool
    call costs one small file read and nothing else.
    """
    import random

    from life_graph.integrations.claude_code.policy import (
        DailyCounter,
        build_observation,
        format_observation,
        is_low_signal,
    )

    tool_name = payload.get("tool_name")
    if not tool_name:
        return None

    exit_status = (
        "error"
        if payload.get("hook_event_name") == "PostToolUseFailure"
        else _tool_exit_status(payload)
    )
    duration = payload.get("duration_ms")
    observation = build_observation(
        tool_name=str(tool_name),
        tool_input=payload.get("tool_input"),
        exit_status=exit_status,
        duration_ms=int(duration) if isinstance(duration, (int, float)) else 0,
        extra={"tool_use_id": payload.get("tool_use_id")},
    )
    if payload.get("error"):
        observation["error"] = str(payload["error"])[:500]

    low_signal = is_low_signal(observation)
    counter = DailyCounter(cfg.counter_path)
    if not counter.check_and_increment(
        low_signal=low_signal,
        daily_cap=cfg.daily_cap,
        sample_rate=cfg.sample_rate,
        rng=rng or random.random,
    ):
        _log(cfg, "throttled", tool=tool_name, count=counter.current())
        return None

    _capture(
        payload,
        cfg,
        surface=SURFACE_TOOL_EXHAUST,
        content=format_observation(observation),
        properties=observation,
        client=client,
    )
    return None


def handle_stop(payload: dict[str, Any], cfg: HookConfig, *, client=None) -> dict[str, Any] | None:
    """Capture the assistant's closing message — surface ``assistant_message``.

    High-signal by definition (it is a conclusion, not routine noise), so it
    bypasses the low-signal sampler. A trivially short message is dropped.

    Its own surface rather than ``tool_exhaust``: that one is a raw activity
    trail which the capture spine deliberately does not extract, and a
    conclusion is the one thing arriving from this integration that is worth
    remembering. Both are VERIFIED, so nothing about fencing changes.
    """
    message = (payload.get("last_assistant_message") or "").strip()
    if len(message) < MIN_ASSISTANT_MESSAGE_CHARS:
        return None
    props: dict[str, Any] = {"kind": "assistant_message"}
    if payload.get("agent_type"):
        props["agent_type"] = payload["agent_type"]
    _capture(
        payload,
        cfg,
        surface=SURFACE_ASSISTANT_MESSAGE,
        content=message,
        properties=props,
        client=client,
    )
    return None


def handle_session_end(
    payload: dict[str, Any], cfg: HookConfig, *, client=None
) -> dict[str, Any] | None:
    """Flush the offline spool on the way out, within a hard time budget."""
    from life_graph.integrations.claude_code.transport import flush_spool

    sent = flush_spool(cfg, client=client, limit_seconds=FLUSH_BUDGET_SECONDS)
    _log(cfg, "session_end", reason=payload.get("reason"), flushed=sent)
    return None


HANDLERS = {
    "SessionStart": handle_session_start,
    "UserPromptSubmit": handle_user_prompt_submit,
    "PostToolUse": handle_post_tool_use,
    "PostToolUseFailure": handle_post_tool_use,
    "Stop": handle_stop,
    "SubagentStop": handle_stop,
    "SessionEnd": handle_session_end,
}


# ── Entrypoint ───────────────────────────────────────────────────────────


def dispatch(payload: dict[str, Any], cfg: HookConfig, *, client=None) -> dict[str, Any] | None:
    """Route one hook payload to its handler. Unknown events are a no-op."""
    handler = HANDLERS.get(payload.get("hook_event_name") or "")
    if handler is None:
        return None
    return handler(payload, cfg, client=client)


def main(stdin=None, stdout=None) -> int:
    """Read one hook event, act on it, and always exit 0.

    Returns the process exit code (always 0). Nonzero would surface a hook
    error to the developer; exit 2 would block their action outright.
    """
    stdin = stdin if stdin is not None else sys.stdin
    stdout = stdout if stdout is not None else sys.stdout
    cfg = None
    try:
        raw = stdin.read()
        payload = json.loads(raw) if raw and raw.strip() else None
        if not isinstance(payload, dict):
            return 0

        cfg = load_config()
        if cfg.disabled:
            return 0
        # Windows Claude Code hands a Windows cwd to a hook running in WSL.
        if isinstance(payload.get("cwd"), str):
            payload["cwd"] = normalize_path(payload["cwd"])
        # Out-of-scope sessions: no capture and no recall injected either.
        if not in_project_roots(payload.get("cwd"), cfg.project_roots):
            return 0

        output = dispatch(payload, cfg)
        if output:
            stdout.write(json.dumps(output))
            stdout.flush()
    except Exception as exc:  # noqa: BLE001 - a hook must never propagate
        if cfg is not None:
            _log(cfg, "error", error=f"{type(exc).__name__}: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

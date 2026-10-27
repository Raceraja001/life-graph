"""How one chat turn was made (web-chat-wave1 F3): route, models, memories, tools.

``build_trace`` is stored on the turn (``AgentTask.result["trace"]``) and read by
``GET /jarvis/turns/{id}/trace``; ``summary_line`` is the one line under a reply
("Local · 3 memories · 2 tools"). Only what explains the answer is kept: a
memory's id and the start of its text, a tool's name, outcome and time — never
a tool's arguments or results, which can hold anything.
"""

from __future__ import annotations

from typing import Any

SNIPPET_CHARS = 60


def _snippet(text: str) -> str:
    flat = " ".join((text or "").split())
    return flat if len(flat) <= SNIPPET_CHARS else flat[: SNIPPET_CHARS - 1] + "…"


def build_trace(
    route: dict[str, Any] | None,
    model_calls: list[dict[str, Any]],
    memories: list[dict[str, Any]],
    tool_calls: list[dict[str, Any]],
) -> dict[str, Any]:
    route = route or {}
    return {
        "route": {
            "kind": route.get("kind"),
            "model": route.get("model"),
            "reason": route.get("reason") or "",
        },
        # Local only when it is known that every model call stayed local.
        "local": bool(model_calls) and all(c.get("local") is True for c in model_calls),
        "models": [str(c.get("model")) for c in model_calls if c.get("model")],
        "memories": [
            {"id": str(m["id"]), "snippet": _snippet(str(m.get("content") or ""))}
            for m in memories
            if m.get("id") is not None
        ],
        "tools": [
            {"name": str(t.get("name")), "ok": bool(t.get("ok")), "ms": int(t.get("ms") or 0)}
            for t in tool_calls
        ],
    }


def _count(n: int, one: str, many: str) -> str:
    if n == 0:
        return f"no {many}"
    return f"{n} {one if n == 1 else many}"


def summary_line(trace: dict[str, Any]) -> str:
    if trace.get("local"):
        where = "Local"
    else:
        reason = (trace.get("route") or {}).get("reason") or ""
        where = f"Cloud ({reason})" if reason else "Cloud"
    return " · ".join(
        [
            where,
            _count(len(trace.get("memories") or []), "memory", "memories"),
            _count(len(trace.get("tools") or []), "tool", "tools"),
        ]
    )


def tool_ok(result: Any) -> bool:
    """A tool result reads as failed when it is a JSON object with an ``error``."""
    import json

    try:
        parsed = json.loads(str(result))
    except (TypeError, ValueError):
        return True
    return not (isinstance(parsed, dict) and parsed.get("error"))

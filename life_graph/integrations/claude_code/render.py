"""Render a ``RecallContext`` into compact markdown for ``additionalContext``.

Whatever this returns is prepended to the model's context at session start, so
it is charged on every subsequent turn of the session. It is therefore kept
short and structured: one heading, four optional bullet groups, hard caps on
both item count and item length. Raw JSON would cost several times as many
tokens to say the same thing.
"""

from __future__ import annotations

from typing import Any

#: Section order matters — identity frames everything that follows.
_SECTIONS: list[tuple[str, str]] = [
    ("identity", "Who you are working with"),
    ("decisions", "Past decisions"),
    ("warnings", "Warnings & lessons"),
    ("intentions", "Open intentions"),
]

MAX_ITEMS_PER_SECTION = 5
MAX_ITEM_CHARS = 240
HEADING = "## Recalled from Life Graph"


def _one_line(text: str) -> str:
    """Collapse whitespace and clip, so one memory is always one bullet."""
    flat = " ".join(str(text).split())
    if len(flat) > MAX_ITEM_CHARS:
        flat = flat[: MAX_ITEM_CHARS - 1].rstrip() + "…"
    return flat


def _bullet(item: Any) -> str | None:
    """Format one memory or intention as a bullet, or None if it has no content."""
    if not isinstance(item, dict):
        return None
    content = item.get("content")
    if not content or not str(content).strip():
        return None
    prefix = ""
    priority = item.get("priority")
    if priority:
        prefix = f"[{priority}] "
    return f"- {prefix}{_one_line(content)}"


def render_recall(recall: dict[str, Any] | None) -> str:
    """Render recall into markdown. Empty string when there is nothing to say.

    An empty string is meaningful: the hook then emits no ``additionalContext``
    at all rather than an empty heading, keeping a cold Life Graph invisible.
    """
    if not isinstance(recall, dict):
        return ""

    blocks: list[str] = []
    for key, title in _SECTIONS:
        items = recall.get(key)
        if not isinstance(items, list):
            continue
        bullets = [b for b in (_bullet(i) for i in items[:MAX_ITEMS_PER_SECTION]) if b]
        if bullets:
            blocks.append(f"**{title}**\n" + "\n".join(bullets))

    if not blocks:
        return ""
    return f"{HEADING}\n\n" + "\n\n".join(blocks)


def summarize_counts(recall: dict[str, Any] | None) -> str:
    """One-line ``systemMessage`` describing what was injected."""
    if not isinstance(recall, dict):
        return ""
    parts = [
        f"{len(recall.get(key) or [])} {key}"
        for key, _ in _SECTIONS
        if isinstance(recall.get(key), list) and recall.get(key)
    ]
    if not parts:
        return ""
    return "Life Graph recall: " + ", ".join(parts)

"""Chat history helpers (docs/specs/web-chat-wave1.md F6): search snippets and
which turns a regeneration replaced.

A regenerated turn is a new top-level AgentTask whose ``input.regenerates``
names the turn it re-ran. Both versions stay in the conversation; only the
newer one, once it completed, is what the persona is shown next
(api/kernel.py ``_load_chat_history``) and what the list of messages marks as
the current reply (api/jarvis.py ``messages``).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterable

#: Longest ``match`` snippet a search result carries.
SNIPPET_CHARS = 120
#: The words of a search query, as plainto_tsquery('simple', ...) splits them
#: closely enough for finding where to cut a snippet.
_WORD = re.compile(r"\w+", re.UNICODE)


def superseded_by(turns: Iterable[Any]) -> dict[str, str]:
    """``{replaced turn id: the turn that replaced it}`` among these turns.

    Only a regeneration that completed replaces anything: one that failed or
    is still running leaves the original as the conversation's answer. The
    chain is followed through versions that did not complete (A, then B
    regenerating A failed, then C regenerating B: C replaces A and B). When a
    turn was regenerated more than once, the newest completed version wins
    (turns are read in the order given, oldest first).
    """
    turns = list(turns)
    parent = {
        str(t.id): str(r)
        for t in turns
        if (r := (getattr(t, "input", None) or {}).get("regenerates"))
    }
    out: dict[str, str] = {}
    for t in turns:
        if getattr(t, "status", None) != "completed":
            continue
        seen: set[str] = set()
        at = parent.get(str(t.id))
        while at and at not in seen:
            seen.add(at)
            out[at] = str(t.id)
            at = parent.get(at)
    return out


def versions_of(turns: Iterable[Any], turn_id: object) -> set[str]:
    """``turn_id`` and every earlier version it regenerated, among these turns."""
    parent = {
        str(t.id): str(r)
        for t in turns
        if (r := (getattr(t, "input", None) or {}).get("regenerates"))
    }
    out: set[str] = set()
    at: str | None = str(turn_id)
    while at and at not in out:
        out.add(at)
        at = parent.get(at)
    return out


def snippet(text: str, query: str, limit: int = SNIPPET_CHARS) -> str:
    """At most ``limit`` characters of ``text`` around the first query word in it.

    Whitespace is collapsed; a cut end is marked with an ellipsis (counted in
    the limit). With no query word in the text, its start.
    """
    flat = " ".join((text or "").split())
    if len(flat) <= limit:
        return flat
    lowered = flat.casefold()
    hit = -1
    for word in _WORD.findall(query or ""):
        at = lowered.find(word.casefold())
        if at >= 0 and (hit < 0 or at < hit):
            hit = at
    room = limit - 2  # an ellipsis at each end, at most
    start = 0 if hit < 0 else max(0, hit - room // 3)
    start = min(start, len(flat) - room)
    if start <= 1:
        return flat[: limit - 1].rstrip() + "…"
    end = start + room
    if end >= len(flat):
        return "…" + flat[len(flat) - (limit - 1) :].lstrip()
    return "…" + flat[start:end].strip() + "…"

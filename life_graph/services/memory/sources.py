"""Where a memory came from, in words the owner reads.

Used by the Jarvis memory views (api/jarvis.py, services/jarvis_memory.py,
services/jarvis_today.py, services/memory/page.py). Lived in api/jarvis.py
until 2026-11-16, which made three services import a route module for it.
"""

from __future__ import annotations

SOURCE_LABEL = {
    "cli": "Claude Code",
    "jarvis_app": "Jarvis",
    "explicit": "Jarvis",
    "voice": "voice",
    "telegram": "Telegram",
    "dashboard": "dashboard",
    "manual": "dashboard",
    "image": "an image",
    "interview_answer": "interview",
}


def source_label(m) -> str:
    """The label for a memory's surface, else its source type, else Life Graph."""
    props = m.properties or {}
    for key in (props.get("surface"), m.source_type):
        if key in SOURCE_LABEL:
            return SOURCE_LABEL[key]
    return "Life Graph"

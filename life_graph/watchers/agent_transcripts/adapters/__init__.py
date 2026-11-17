"""Transcript adapters, one per coding agent, and the registry over them.

Adding support for another agent is one module here plus one entry in
:data:`ADAPTER_CLASSES` — nothing downstream of the canonical event
vocabulary (normalizer, watcher, distiller, CLI) changes.
"""

from __future__ import annotations

from life_graph.watchers.agent_transcripts.adapters.antigravity import AntigravityAdapter
from life_graph.watchers.agent_transcripts.adapters.base import BaseTranscriptAdapter
from life_graph.watchers.agent_transcripts.adapters.claude_code import ClaudeCodeAdapter
from life_graph.watchers.agent_transcripts.adapters.codex import CodexAdapter
from life_graph.watchers.agent_transcripts.adapters.cursor import CursorAdapter

#: Discovery order. Claude Code first because its glob is the widest, so a
#: directory holding two agents' logs has its files claimed by the adapter
#: that can actually read them (the watcher reads each path once).
ADAPTER_CLASSES: tuple[type[BaseTranscriptAdapter], ...] = (
    ClaudeCodeAdapter,
    AntigravityAdapter,
    CursorAdapter,
    CodexAdapter,
)

#: CLI-friendly aliases: ``--agent claude`` means ``claude_code``.
AGENT_ALIASES: dict[str, str] = {
    "claude": ClaudeCodeAdapter.agent_type,
    "claude-code": ClaudeCodeAdapter.agent_type,
    "claude_code": ClaudeCodeAdapter.agent_type,
    "antigravity": AntigravityAdapter.agent_type,
    "gemini": AntigravityAdapter.agent_type,
    "cursor": CursorAdapter.agent_type,
    "codex": CodexAdapter.agent_type,
    "openclaw": CodexAdapter.agent_type,
}


def all_adapters() -> list[BaseTranscriptAdapter]:
    """One instance of every registered adapter, in discovery order."""
    return [cls() for cls in ADAPTER_CLASSES]


def adapters_for(agent: str | None) -> list[BaseTranscriptAdapter]:
    """Adapters for *agent* (name or alias); all of them when *agent* is falsy.

    Raises:
        ValueError: *agent* matches no adapter — better than silently
            harvesting everything when a flag is misspelled.
    """
    if not agent:
        return all_adapters()
    resolved = AGENT_ALIASES.get(agent.strip().lower().replace(" ", "_"))
    chosen = [cls() for cls in ADAPTER_CLASSES if cls.agent_type == resolved]
    if not chosen:
        known = ", ".join(sorted(AGENT_ALIASES))
        raise ValueError(f"Unknown agent {agent!r}. Known: {known}")
    return chosen


__all__ = [
    "ADAPTER_CLASSES",
    "AGENT_ALIASES",
    "AntigravityAdapter",
    "BaseTranscriptAdapter",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "CursorAdapter",
    "adapters_for",
    "all_adapters",
]

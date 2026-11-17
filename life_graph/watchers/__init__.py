"""Ambient AI Watcher Framework (Era 6).

Provides background watchers for server health, code quality,
tech radar, coding-agent transcripts, and notification routing.
"""

from life_graph.watchers.agent_transcripts.watcher import AgentTranscriptWatcher

__all__ = ["AgentTranscriptWatcher"]

"""Multi-agent transcript harvester.

Coding agents (Claude Code, Cursor, Antigravity, Codex) each leave a JSONL
transcript of every session on disk. That trail is the most detailed record
there is of how work actually got done — which command failed, what the fix
was — and it was being thrown away.

This package reads those transcripts incrementally and turns each user turn
into one agent-agnostic :class:`NormalizedSessionSlice`:

* :mod:`.adapters` — one module per agent: where its transcripts live, and
  what its records mean. The only place a vendor's field names appear.
* :mod:`.normalizer` — folds canonical events into per-turn slices, flagging
  the ones that hit errors and the ones that recovered.
* :mod:`.watermark` — per-file byte offsets, so a pass reads only new bytes.
* :mod:`.harvest` — the shared traversal used by both the watcher and the CLI.
* :mod:`.watcher` — the scheduled watcher: ingest to the capture spine, then
  hand candidates to ``services.skill_distiller`` for distillation.
"""

from life_graph.watchers.agent_transcripts.harvest import (
    FileHarvest,
    HarvestScan,
    collect_new_slices,
)
from life_graph.watchers.agent_transcripts.normalizer import (
    NormalizedSessionSlice,
    TranscriptNormalizer,
)
from life_graph.watchers.agent_transcripts.watermark import WatermarkStore

__all__ = [
    "FileHarvest",
    "HarvestScan",
    "NormalizedSessionSlice",
    "TranscriptNormalizer",
    "WatermarkStore",
    "collect_new_slices",
]

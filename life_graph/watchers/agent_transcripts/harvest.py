"""Discovery → incremental read → normalize, shared by the watcher and the CLI.

Both callers need the same traversal (which files are new, which bytes are
new, what slices came out) and differ only in what they do with the result:
the watcher ingests and distills, the CLI may just print it. Keeping the
traversal here means ``--dry-run`` exercises the same code path that the
cron does, rather than a second implementation of it.

Nothing here touches the database or the network, so the whole module is
usable with no running stack.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from life_graph.watchers.agent_transcripts.adapters import BaseTranscriptAdapter, all_adapters
from life_graph.watchers.agent_transcripts.normalizer import (
    NormalizedSessionSlice,
    TranscriptNormalizer,
)
from life_graph.watchers.agent_transcripts.watermark import (
    DEFAULT_SETTLING_SECONDS,
    WatermarkStore,
)

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

#: Files read per pass. A first run over a years-old ``~/.claude/projects``
#: would otherwise read hundreds of transcripts in one go; the watcher runs
#: every 15 minutes, so the backlog drains in order (oldest first) instead.
DEFAULT_FILE_LIMIT = 25


@dataclass
class FileHarvest:
    """What one transcript file yielded this pass."""

    path: Path
    agent_type: str
    slices: list[NormalizedSessionSlice] = field(default_factory=list)
    new_offset: int = 0
    previous_offset: int = 0
    mtime: float = 0.0
    session_id: str = ""

    @property
    def bytes_read(self) -> int:
        return max(self.new_offset - self.previous_offset, 0)


@dataclass
class HarvestScan:
    """The result of one traversal, with the counters the callers report on."""

    harvests: list[FileHarvest] = field(default_factory=list)
    files_seen: int = 0
    files_skipped_unsettled: int = 0
    files_up_to_date: int = 0

    @property
    def slices(self) -> list[NormalizedSessionSlice]:
        return [s for h in self.harvests for s in h.slices]


def collect_new_slices(
    adapters: list[BaseTranscriptAdapter] | None = None,
    *,
    store: WatermarkStore | None = None,
    base_dirs: list[Path] | None = None,
    limit: int | None = DEFAULT_FILE_LIMIT,
    settling_seconds: float = DEFAULT_SETTLING_SECONDS,
    normalizer: TranscriptNormalizer | None = None,
) -> HarvestScan:
    """Read every transcript that grew since its watermark and normalize it.

    Watermarks are *read* here and never written: the caller advances them
    only once it has done something durable with the slices, so a crash
    mid-ingest replays the same bytes instead of losing them.
    """
    adapters = adapters if adapters is not None else all_adapters()
    store = store or WatermarkStore()
    normalizer = normalizer or TranscriptNormalizer()

    scan = HarvestScan()
    seen: set[Path] = set()

    for adapter in adapters:
        for path in adapter.find_transcript_files(base_dirs):
            if limit is not None and len(scan.harvests) >= limit:
                return scan
            if path in seen:
                continue
            seen.add(path)
            scan.files_seen += 1

            offset, _last_mtime = store.get_watermark(path)
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size <= offset:
                scan.files_up_to_date += 1
                continue
            if not store.is_settled(path, settling_seconds):
                scan.files_skipped_unsettled += 1
                continue

            raw_events, new_offset = adapter.parse_incremental(path, offset)
            if not raw_events or new_offset <= offset:
                continue

            slices = normalizer.normalize(adapter, path, raw_events)
            scan.harvests.append(
                FileHarvest(
                    path=path,
                    agent_type=adapter.agent_type,
                    slices=slices,
                    new_offset=new_offset,
                    previous_offset=offset,
                    mtime=stat.st_mtime,
                    session_id=slices[0].session_id if slices else path.stem,
                )
            )
    return scan

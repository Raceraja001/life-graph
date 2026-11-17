"""The scheduled harvester: transcripts → capture spine → distilled skills.

Runs every 15 minutes. Each pass reads only the bytes that appeared since the
last one, ingests every new turn into the capture spine, and hands the few
turns that look like a procedure to the skill distiller.

Two ordering rules matter and both are about never losing work:

* a file's watermark advances only *after* its slices are ingested, so a crash
  replays bytes rather than skipping them (the capture spine dedupes on
  content hash, so a replay is cheap and harmless);
* distillation failures are swallowed per slice. A model being down must not
  stop the ingest half, which is the part that cannot be recomputed later.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from life_graph.watchers.agent_transcripts.adapters import adapters_for, all_adapters
from life_graph.watchers.agent_transcripts.harvest import (
    DEFAULT_FILE_LIMIT,
    FileHarvest,
    collect_new_slices,
)
from life_graph.watchers.agent_transcripts.watermark import (
    DEFAULT_SETTLING_SECONDS,
    WatermarkStore,
)
from life_graph.watchers.base import BaseWatcher, Severity, WatchEventData

if TYPE_CHECKING:
    from life_graph.watchers.agent_transcripts.normalizer import NormalizedSessionSlice

#: ``CaptureEvent.surface`` for every turn harvested here. Deliberately absent
#: from ``core/trust.py``'s surface map, so it classifies EXTERNAL: a
#: transcript is mostly tool output and quoted files, not the owner's words.
SURFACE = "coding_agent"

#: ``CaptureEvent.modality`` for every turn harvested here.
MODALITY = "transcript"


class AgentTranscriptWatcher(BaseWatcher):
    """Harvests coding-agent transcripts and distils procedural skills from them.

    Settings (``watch_configs.config``), all optional:

    ``agents``
        Agent names to harvest (default: every adapter).
    ``base_dirs``
        Directories to search instead of each adapter's default location.
    ``state_path``
        Where the watermark file lives.
    ``file_limit``
        Files read per pass (default :data:`DEFAULT_FILE_LIMIT`).
    ``settling_seconds``
        How long a file must be untouched before it is read.
    ``distill``
        Set False to ingest only and skip the LLM half entirely.
    """

    name = "agent_transcripts"
    display_name = "Agent Transcripts Harvester"
    default_schedule = "*/15 * * * *"

    async def execute(self) -> list[WatchEventData]:
        """Harvest every transcript that grew, then distil the candidates.

        Returns the events it emitted. ``BaseWatcher.run()`` reads them off
        ``self._events`` and ignores the return value; it is returned for the
        benefit of direct callers (the CLI, tests).
        """
        config = self.settings or {}
        store = WatermarkStore(state_path=config.get("state_path"))
        scan = collect_new_slices(
            self._adapters(config),
            store=store,
            base_dirs=config.get("base_dirs"),
            limit=int(config.get("file_limit", DEFAULT_FILE_LIMIT)),
            settling_seconds=float(config.get("settling_seconds", DEFAULT_SETTLING_SECONDS)),
        )

        distiller = self._distiller() if config.get("distill", True) else None
        advanced = False
        captured = 0
        candidates = 0
        created: list[str] = []
        patched: list[str] = []

        for harvest in scan.harvests:
            ingested = await self._ingest(harvest)
            captured += ingested

            # Only now is the file's progress durable — and only if every turn
            # landed. A turn lost to a transient database failure is replayed
            # next pass; the capture spine dedupes on content hash, so the cost
            # of re-reading is nothing against the cost of dropping history.
            if ingested < len(harvest.slices):
                self.logger.warning(
                    "Holding the watermark for %s: %d of %d turn(s) ingested",
                    harvest.path,
                    ingested,
                    len(harvest.slices),
                )
                continue
            store.update_watermark(
                harvest.path, harvest.new_offset, harvest.mtime, harvest.session_id
            )
            advanced = True

            if distiller is None:
                continue
            for session_slice in harvest.slices:
                if not distiller.filter_candidate(session_slice):
                    continue
                candidates += 1
                result = await self._distill(distiller, session_slice)
                if result is None:
                    continue
                if result.created:
                    created.append(str(result.skill.get("title") or result.memory_id))
                elif result.patched:
                    patched.append(str(result.memory_id))

        if advanced:
            store.save()

        self._report(scan, captured, candidates, created, patched)
        return list(self._events)

    # ── Steps ─────────────────────────────────────────────────

    @staticmethod
    def _adapters(config: dict[str, Any]):
        """The adapters this run should use, from ``settings["agents"]``."""
        agents = config.get("agents")
        if not agents:
            return all_adapters()
        if isinstance(agents, str):
            agents = [agents]
        chosen = []
        for agent in agents:
            try:
                chosen.extend(adapters_for(agent))
            except ValueError:
                continue
        return chosen or all_adapters()

    def _distiller(self):
        """The skill distiller, or None when it cannot be constructed."""
        try:
            from life_graph.services.skill_distiller import SkillDistillationEngine

            return SkillDistillationEngine(self.tenant_id, session_factory=self.session_factory)
        except Exception:  # noqa: BLE001 - ingest must survive without it
            self.logger.warning("Skill distiller unavailable — ingesting only", exc_info=True)
            return None

    async def _ingest(self, harvest: FileHarvest) -> int:
        """Ingest one file's slices as capture events. Returns how many landed."""
        from life_graph.services.capture import CaptureService, without_nul

        if not harvest.slices:
            return 0

        ingested = 0
        async with self.session_factory() as session:
            service = CaptureService(session)
            for session_slice in harvest.slices:
                try:
                    await service.ingest(
                        tenant_id=self.tenant_id,
                        surface=SURFACE,
                        modality=MODALITY,
                        content=without_nul(session_slice.to_capture_content()),
                        occurred_at=session_slice.occurred_at,
                        properties=without_nul(self.capture_properties(session_slice)),
                    )
                    ingested += 1
                except Exception:  # noqa: BLE001 - one bad turn must not stop the file
                    self.logger.warning(
                        "Could not ingest a turn of %s", harvest.path, exc_info=True
                    )
            await session.commit()
        return ingested

    @staticmethod
    def capture_properties(session_slice: NormalizedSessionSlice) -> dict[str, Any]:
        """``CaptureEvent.properties`` for one harvested turn."""
        return {
            "agent_type": session_slice.agent_type,
            "project": session_slice.project_name,
            "session_id": session_slice.session_id,
            "has_errors": session_slice.has_errors,
            "has_fixes": session_slice.has_fixes,
            "file_path": session_slice.file_path,
            "tool_count": len(session_slice.tool_calls or []),
        }

    async def _distill(self, distiller, session_slice: NormalizedSessionSlice):
        """Distil one candidate, swallowing failures (the ingest already landed)."""
        try:
            return await distiller.distill(session_slice)
        except Exception:  # noqa: BLE001
            self.logger.warning(
                "Distilling %s session %s failed",
                session_slice.agent_type,
                session_slice.session_id,
                exc_info=True,
            )
            return None

    def _report(
        self,
        scan,
        captured: int,
        candidates: int,
        created: list[str],
        patched: list[str],
    ) -> None:
        """Emit the pass's findings. A pass that found nothing stays silent."""
        if created:
            self.emit_event(
                Severity.IMPORTANT,
                f"Distilled {len(created)} new procedural skill(s) from coding sessions",
                details={"skills": created, "patched": patched, "candidates": candidates},
                summary="; ".join(created[:5]),
            )
        if not (captured or created or patched):
            return
        self.emit_event(
            Severity.INFO,
            f"Harvested {captured} coding-session turn(s) from {len(scan.harvests)} transcript(s)",
            details={
                "files_seen": scan.files_seen,
                "files_read": len(scan.harvests),
                "files_up_to_date": scan.files_up_to_date,
                "files_unsettled": scan.files_skipped_unsettled,
                "turns_captured": captured,
                "distillation_candidates": candidates,
                "skills_created": len(created),
                "skills_patched": len(patched),
                "agents": sorted({h.agent_type for h in scan.harvests}),
            },
        )

"""Capture Spine Processors — EventBus subscribers for CAPTURE_RECEIVED.

Handles text extraction, decision detection, and procedure candidate
identification from incoming capture events. Follows the
PreferenceGraphService pattern for subscription lifecycle.
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from life_graph.config import settings
from life_graph.core.events import Event, EventBus, EventType, event_bus
from life_graph.storage.database import async_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from life_graph.extraction.rules import ExtractedFact
    from life_graph.models.db import CaptureEvent

logger = logging.getLogger(__name__)

# ── Decision detection patterns ────────────────────────────────────────
# These fire DECISION_CANDIDATE for the Judgment Engine to consume.
_DECISION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\b(?:I|we)\s+decided\s+(?:to\s+)?(.+)", re.IGNORECASE),
    re.compile(r"\b(?:I|we)(?:'re|'ve)?\s+go(?:ing)?\s+with\s+(.+)", re.IGNORECASE),
    re.compile(r"\bthe\s+plan\s+is\s+(?:to\s+)?(.+)", re.IGNORECASE),
    re.compile(r"\blet'?s\s+(?:go\s+with|use|do|try)\s+(.+)", re.IGNORECASE),
    re.compile(r"\b(?:I|we)\s+chose\s+(.+)", re.IGNORECASE),
    re.compile(r"\b(?:I|we)\s+switched\s+(?:to|from)\s+(.+)", re.IGNORECASE),
    re.compile(r"\bfinal\s+(?:decision|answer|choice)\s*[:=]\s*(.+)", re.IGNORECASE),
    re.compile(r"\bafter\s+(?:thinking|considering).*?\b(?:I|we)\s+will\s+(.+)", re.IGNORECASE),
]

# ── Procedure detection ────────────────────────────────────────────────
# Tracks repeated action sequences. Fires PROCEDURE_CANDIDATE when
# the same trajectory is seen 3+ times in 30 days.
# (Phase 4 implements the full trajectory tracking; this phase detects
# explicit procedure-like statements.)
_PROCEDURE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bevery\s+time\s+I\s+(.+?)(?:,\s*I\s+(.+))", re.IGNORECASE),
    re.compile(r"\bI\s+always\s+(?:start|begin)\s+by\s+(.+)", re.IGNORECASE),
    re.compile(
        r"\bmy\s+(?:usual\s+)?(?:process|workflow|routine)\s+(?:is|for)\s+(.+)", re.IGNORECASE
    ),
    re.compile(r"\bstep\s+\d+\s*[:.]?\s*(.+)", re.IGNORECASE),
]


class CaptureProcessors:
    """Subscribes to CAPTURE_RECEIVED and runs extraction processors.

    Processors:
      1. Text extraction via ExtractionPipeline (Tier 1-3)
      2. Decision candidate detection (regex → DECISION_CANDIDATE)
      2b. Explicit confidence claims → suggested predictions
      3. Procedure candidate detection (regex → PROCEDURE_CANDIDATE)
    """

    def __init__(self, bus: EventBus | None = None) -> None:
        self._bus = bus or event_bus
        self._subscribed = False

    def subscribe(self) -> None:
        """Register as a CAPTURE_RECEIVED handler. Idempotent."""
        if self._subscribed:
            return
        self._bus.subscribe(EventType.CAPTURE_RECEIVED, self._on_capture_received)
        self._subscribed = True
        logger.info("CaptureProcessors subscribed to EventBus")

    def unsubscribe(self) -> None:
        """Remove subscription."""
        if not self._subscribed:
            return
        self._bus.unsubscribe(EventType.CAPTURE_RECEIVED, self._on_capture_received)
        self._subscribed = False

    async def _on_capture_received(self, event: Event) -> None:
        """Process a newly captured event — extract, detect decisions, update yield."""
        payload = event.payload
        capture_event_id = payload.get("capture_event_id")
        tenant_id = payload.get("tenant_id")
        modality = payload.get("modality", "text")

        if modality != "text":
            logger.debug("Skipping non-text capture %s (modality=%s)", capture_event_id, modality)
            return

        try:
            async with async_session() as session:
                from life_graph.models.db import CaptureEvent

                result = await session.execute(
                    __import__("sqlalchemy")
                    .select(CaptureEvent)
                    .where(CaptureEvent.id == uuid.UUID(capture_event_id))
                )
                capture_evt = result.scalars().first()
                if not capture_evt:
                    logger.warning("CaptureEvent %s not found", capture_event_id)
                    return

                surface = capture_evt.surface
                if surface in settings.capture_no_extract_surfaces_list:
                    # An activity trail, not content. The event row stays (that
                    # is the trail), but running extraction over it turned every
                    # tool call into several LLM-written "facts" about shell
                    # commands — noise that outnumbered real memories 20:1 and
                    # was what recall then fed back into the next session.
                    capture_evt.status = "processed"
                    await session.commit()
                    logger.debug(
                        "Capture %s: surface=%s is not extracted", capture_event_id, surface
                    )
                    return

                content = capture_evt.content
                yield_count = 0

                # ── 1. Run extraction pipeline ──────────────────────
                facts: list[ExtractedFact] = []
                try:
                    from life_graph.api.dependencies import get_extraction_pipeline

                    # The shared pipeline, not a fresh ExtractionPipeline(): a
                    # bare one builds an LLMExtractor with no local client and a
                    # hardcoded cloud model default, so tier 3 called a provider
                    # this deployment may not even have keys for.
                    #
                    # capture=True because a CaptureEvent *is* a genuine user
                    # capture (voice, chat, note) — the same flag the /memories
                    # route passes. Without it the capture spine, the ambient
                    # path that produces most memories, silently got the weaker
                    # regex/spaCy result while the API path got LLM-first output.
                    extraction = await get_extraction_pipeline().extract(content, capture=True)
                    facts = list(extraction.facts)
                    logger.info(
                        "Extraction from capture %s: %d facts (T1=%d T2=%d T3=%d)",
                        capture_event_id,
                        len(extraction.facts),
                        extraction.tier1_count,
                        extraction.tier2_count,
                        extraction.tier3_count,
                    )
                except Exception:
                    logger.warning(
                        "Extraction pipeline failed for %s", capture_event_id, exc_info=True
                    )

                # ── 1b. Persist those facts as memories ─────────────
                # Extraction alone yields nothing durable — the facts have to
                # go through MemoryManager (embed → dedup → score → pending
                # gate) to become memories. Only what actually lands counts
                # towards the capture's yield.
                if facts:
                    yield_count += await self._store_memories(facts, capture_evt, tenant_id)

                # ── 2. Decision candidate detection ─────────────────
                decisions = self._detect_decisions(content)
                for decision_text in decisions:
                    yield_count += 1
                    await self._bus.emit(
                        EventType.DECISION_CANDIDATE,
                        {
                            "capture_event_id": capture_event_id,
                            "tenant_id": tenant_id,
                            "title": decision_text[:200],
                            "reasoning": content[:500],
                            "source": "conversation",
                        },
                    )
                    logger.info("Decision candidate detected: %s", decision_text[:80])

                # ── 2b. Prediction suggestions ──────────────────────
                yield_count += await self._suggest_predictions(
                    session, content, capture_evt, tenant_id
                )

                # ── 3. Procedure candidate detection ────────────────
                procedures = self._detect_procedures(content)
                for proc_text in procedures:
                    yield_count += 1
                    await self._bus.emit(
                        EventType.PROCEDURE_CANDIDATE,
                        {
                            "capture_event_id": capture_event_id,
                            "tenant_id": tenant_id,
                            "description": proc_text[:200],
                        },
                    )
                    logger.info("Procedure candidate detected: %s", proc_text[:80])

                # ── 4. Update yield count ───────────────────────────
                if yield_count > 0:
                    capture_evt.yield_count = (capture_evt.yield_count or 0) + yield_count
                    capture_evt.status = "processed"
                else:
                    capture_evt.status = "processed"

                await session.commit()

        except Exception:
            logger.error("CaptureProcessor failed for %s", capture_event_id, exc_info=True)

    async def _store_memories(
        self,
        facts: list[ExtractedFact],
        capture_evt: CaptureEvent,
        tenant_id: str | None,
    ) -> int:
        """Persist extracted facts as memories; return how many were stored.

        The trust tier recorded on the capture event (derived default-deny from
        its surface) is threaded through to every memory, so facts from
        EXTERNAL / HOSTILE_POSSIBLE surfaces stay marked as untrusted. Every new
        memory lands ``pending`` behind the existing approval gate regardless of
        tier — that policy lives in ``PostgresMemoryStore.store``.

        Failures are logged and swallowed: memory persistence must never break
        capture ingestion.

        Args:
            facts: Facts produced by the extraction pipeline.
            capture_evt: The originating ``CaptureEvent`` row.
            tenant_id: Tenant from the event payload, used to set the tenant
                contextvar when this handler runs outside a request.

        Returns:
            Number of memories actually stored (post-dedup), 0 on failure.
        """
        try:
            from life_graph.api.dependencies import get_memory_manager
            from life_graph.core.tenant import has_tenant_context, set_tenant_context
            from life_graph.core.trust import classify_surface, coerce_tier

            # EventBus handlers can run outside a request (worker, cron), where
            # the tenant contextvar the storage layer reads is unset.
            if tenant_id and not has_tenant_context():
                set_tenant_context(tenant_id, "system")

            surface = getattr(capture_evt, "surface", None)
            # The row's tier is authoritative when present (a caller may have
            # asserted something stricter than the surface implies, e.g. a
            # watcher carrying a raw web body); otherwise classify the surface,
            # which is default-deny — unknown surfaces resolve to EXTERNAL.
            tier = coerce_tier(
                getattr(capture_evt, "trust_tier", None),
                default=classify_surface(surface),
            )

            memories = await get_memory_manager().store_facts(
                facts,
                context={
                    "capture_event_id": str(capture_evt.id),
                    "surface": surface,
                },
                source="capture",
                trust_tier=tier.value,
            )
            logger.info(
                "Capture %s: stored %d/%d facts as memories (trust_tier=%s)",
                capture_evt.id,
                len(memories),
                len(facts),
                tier.value,
            )
            return len(memories)
        except Exception:
            logger.warning(
                "Memory persistence failed for capture %s", capture_evt.id, exc_info=True
            )
            return 0

    async def _suggest_predictions(
        self,
        session: AsyncSession,
        content: str,
        capture_evt: CaptureEvent,
        tenant_id: str | None,
    ) -> int:
        """Store explicit confidence claims as suggested predictions.

        Only the user's own words count: a claim quoted from an external
        surface ("70% chance of rain") is not the user's prediction. Each
        suggestion waits on the Calibration page for accept/dismiss; nothing
        reaches calibration without that. Returns how many were stored.
        """
        if not tenant_id:
            return 0
        try:
            from life_graph.core.trust import TrustTier, classify_surface, coerce_tier
            from life_graph.services.judgment import JudgmentService
            from life_graph.services.prediction_detection import detect_predictions

            surface = getattr(capture_evt, "surface", None)
            tier = coerce_tier(
                getattr(capture_evt, "trust_tier", None),
                default=classify_surface(surface),
            )
            if tier not in (TrustTier.SELF, TrustTier.VERIFIED):
                return 0

            now = getattr(capture_evt, "created_at", None) or datetime.now(UTC)
            svc = JudgmentService(session, self._bus)
            stored = 0
            for found in detect_predictions(content, now):
                if await svc.has_open_prediction(tenant_id, found.statement):
                    continue
                await svc.create_prediction(
                    tenant_id=tenant_id,
                    statement=found.statement,
                    confidence=found.confidence,
                    resolve_by=found.resolve_by,
                    resolution_criteria={"type": "manual", "quote": found.quote},
                    capture_event_id=capture_evt.id,
                    suggested=True,
                )
                stored += 1
                logger.info("Prediction suggested: %s", found.statement[:80])
            return stored
        except Exception:
            logger.warning(
                "Prediction detection failed for capture %s", capture_evt.id, exc_info=True
            )
            return 0

    @staticmethod
    def _detect_decisions(text: str) -> list[str]:
        """Extract decision statements from text using regex patterns."""
        decisions: list[str] = []
        seen: set[str] = set()
        for pattern in _DECISION_PATTERNS:
            for match in pattern.finditer(text):
                decision = match.group(1).strip().rstrip(".,;!?")
                normalised = decision.lower()
                if normalised and normalised not in seen and len(decision) > 5:
                    decisions.append(decision)
                    seen.add(normalised)
        return decisions

    @staticmethod
    def _detect_procedures(text: str) -> list[str]:
        """Extract procedure-like statements from text."""
        procedures: list[str] = []
        seen: set[str] = set()
        for pattern in _PROCEDURE_PATTERNS:
            for match in pattern.finditer(text):
                proc = match.group(1).strip().rstrip(".,;!?")
                normalised = proc.lower()
                if normalised and normalised not in seen and len(proc) > 5:
                    procedures.append(proc)
                    seen.add(normalised)
        return procedures


# ── Module-level singleton ─────────────────────────────────────────────
capture_processors = CaptureProcessors()

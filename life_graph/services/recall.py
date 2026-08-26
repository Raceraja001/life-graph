"""Proactive recall engine for push-based memory surfacing (T-022, T-024).

Orchestrates the three-stage recall pipeline:
  1. Retrieve — query store for active memories matching context
  2. Rank — apply multi-signal scoring
  3. Rerank — diversity-aware filtering

Includes anti-annoyance controls: cooldown periods, session caps,
and dismissal tracking to avoid spamming the user.

Bookkeeping is tied to *disclosure*, not to retrieval
---------------------------------------------------
Two side effects fire when recall hands a memory to a caller: a durable
7-day cooldown (so it is not resurfaced), and ``touch_many`` (which feeds
both the decay horizon and the ``frequency`` ranking signal).

Both belong to the moment the memory's content is actually delivered. A full
recall *is* that moment — the content goes out in the response — so it
records exactly as before. An index-only recall is not: it returns a
truncated line so the caller can decide what to ask for, and the caller may
ask for none of it. Recording there would burn a week of cooldown on
memories nobody read and inflate ``access_count`` for every candidate that
was ever merely listed, which is the same class of defect as measuring decay
from ``created_at`` — bookkeeping that describes something other than use.

So ``index_only=True`` records **nothing at all**: no cooldown key, no
touch. Not even a short-TTL key, because a short cooldown protects nothing
(re-listing a memory within the same session is not the nuisance a
next-day resurfacing is) while adding a second TTL to reason about. The
expand step — ``POST /api/v1/memories/batch`` → :meth:`RecallEngine.record_disclosure`
— is where an index-mode surfacing is recorded.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from life_graph.config import settings
from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.schemas import (
    IntentionResponse,
    MemoryIndexItem,
    MemoryResponse,
    RecallContext,
)
from life_graph.scoring.ranking import to_index
from life_graph.services.triggers import TriggerMatcher
from life_graph.storage.redis import get_redis

if TYPE_CHECKING:
    from life_graph.scoring.ranking import RecallRanker
    from life_graph.services.context import ContextBuilder, ContextFingerprint
    from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)

# Cooldown: minimum seconds before resurfacing the same memory
_COOLDOWN_SECONDS: int = settings.recall_cooldown_days * 86400
_MAX_SESSION_SURFACES: int = 10


class RecallEngine:
    """Push-based memory recall engine.

    Proactively surfaces relevant memories at session start and during
    mid-session events, without waiting for the user to search.

    Anti-annoyance controls:
        - Per-memory cooldown (won't resurface within cooldown window)
        - Session surface cap (max total memories surfaced per session)
        - Dismissal tracking (categories dismissed often get deprioritized)

    Usage::

        engine = RecallEngine(store, ranker, context_builder)
        recall = await engine.session_start_recall({"project": "life_graph"})
    """

    def __init__(
        self,
        store: PostgresMemoryStore,
        ranker: RecallRanker,
        context_builder: ContextBuilder,
    ) -> None:
        self._store = store
        self._ranker = ranker
        self._context_builder = context_builder
        self._trigger_matcher = TriggerMatcher(store)

        # Anti-annoyance state (per engine instance = per session)
        #
        # The in-process dict is a cache, not the record. A 7-day cooldown
        # held only here is not a cooldown: it is lost on every restart and
        # every worker keeps its own copy, so a memory suppressed in the web
        # process resurfaces immediately from the ARQ worker or after a
        # deploy. Redis holds the durable copy, keyed per tenant with a TTL
        # equal to the cooldown so it expires itself.
        self._surfaced_memory_ids: dict[str, datetime] = {}
        self._session_surface_count: int = 0
        self._dismissed_categories: Counter[str] = Counter()

    # ── Durable cooldown ──────────────────────────────────────

    @staticmethod
    def _cooldown_key(tenant_id: str, memory_id: str) -> str:
        return f"lg:recall:surfaced:{tenant_id}:{memory_id}"

    async def _remember_surfaced(self, memory_ids: list[str]) -> None:
        """Record a surfacing so other processes and later restarts see it.

        Best-effort in both directions: recall must not fail because Redis is
        unavailable, and a lost key means a memory resurfaces early — mildly
        annoying, never wrong.
        """
        if not memory_ids or _COOLDOWN_SECONDS <= 0:
            return
        redis = get_redis()
        if redis is None:
            return
        try:
            tenant_id = get_current_tenant_id()
            pipe = redis.pipeline()
            for mem_id in memory_ids:
                pipe.setex(self._cooldown_key(tenant_id, mem_id), _COOLDOWN_SECONDS, "1")
            await pipe.execute()
        except Exception:
            logger.debug("Could not persist recall cooldown", exc_info=True)

    async def _on_cooldown(self, memory_ids: list[str]) -> set[str]:
        """Which of *memory_ids* were surfaced recently by ANY process."""
        if not memory_ids or _COOLDOWN_SECONDS <= 0:
            return set()
        redis = get_redis()
        if redis is None:
            return set()
        try:
            tenant_id = get_current_tenant_id()
            keys = [self._cooldown_key(tenant_id, m) for m in memory_ids]
            found = await redis.mget(keys)
        except Exception:
            # Fail open: an unreachable Redis must not block recall entirely.
            logger.debug("Could not read recall cooldown", exc_info=True)
            return set()
        return {mem_id for mem_id, hit in zip(memory_ids, found, strict=False) if hit}

    # ── Main Entry: Session Start ─────────────────────────────

    async def session_start_recall(
        self,
        context: dict[str, Any],
        *,
        index_only: bool = False,
    ) -> RecallContext:
        """Proactively recall memories at session start.

        Pipeline stages:
            1. Build context fingerprint
            2. Retrieve: query store for top-50 active memories
            3. Rank: apply multi-signal scoring
            4. Rerank: diversity-aware filter to max 5
            5. Check triggered intentions
            6. Bundle into RecallContext

        Args:
            context: Raw session context dict.
            index_only: Return a compact index instead of full memory
                objects. Nothing is recorded in this mode — no cooldown, no
                access — because nothing has been disclosed yet; see the
                module docstring.

        Returns:
            RecallContext with identity, decisions, intentions, warnings —
            or, when *index_only*, with ``index`` populated and the four
            buckets empty.
        """
        payload, _ = await self.session_start_recall_measured(context, index_only=index_only)
        return payload

    async def session_start_recall_measured(
        self,
        context: dict[str, Any],
        *,
        index_only: bool = False,
    ) -> tuple[RecallContext, RecallContext | None]:
        """:meth:`session_start_recall`, plus the payload index mode replaced.

        The second element is the full ``RecallContext`` an ``index_only``
        call would otherwise have returned, so the route can report a real
        ``tokens_saved`` rather than an estimate. It is ``None`` in full
        mode, where nothing was saved.

        The pipeline runs **once**. Re-calling
        :meth:`session_start_recall` to obtain the comparison would run the
        retrieval again and — worse — record a surfacing, burning the
        cooldown that index mode exists to protect. Rendering a second view
        of candidates already in memory has no such side effect.
        """
        fingerprint = self._context_builder.build(context)
        logger.info("Session start recall — fingerprint: %s", fingerprint.as_dict())

        # Stage 1: Retrieve candidates
        candidates = await self._retrieve_candidates(fingerprint, limit=50)
        if not candidates:
            logger.info("No candidate memories found for context")

        # Stage 2: Rank
        ranked = self._ranker.rank(candidates, current_context=context)

        # Stage 3: Rerank (max 5)
        reranked = self._ranker.rerank(
            ranked,
            max_results=settings.recall_max_session_start,
        )

        # Filter through anti-annoyance
        filtered = await self._apply_anti_annoyance(reranked)

        # Check intentions (cheap, and useful in both modes)
        triggered_intentions = await self._check_intentions(fingerprint)

        if index_only:
            # Nothing disclosed yet, so nothing recorded. The expand step
            # (record_disclosure) owns the cooldown and the access count.
            index = [MemoryIndexItem.model_validate(item) for item in to_index(filtered)]
            logger.info(
                "Session recall (index): %d entries, %d intentions",
                len(index),
                len(triggered_intentions),
            )
            payload = RecallContext(
                intentions=triggered_intentions,
                result_mode="index",
                index=index,
            )
            return payload, self._as_full_context(filtered, triggered_intentions)

        recall_ctx = self._as_full_context(filtered, triggered_intentions)

        # Full content is going out in this response — that is the
        # disclosure, so record it.
        await self._record_surfacing(filtered)

        logger.info(
            "Session recall: %d identity, %d decisions, %d intentions, %d warnings",
            len(recall_ctx.identity),
            len(recall_ctx.decisions),
            len(recall_ctx.intentions),
            len(recall_ctx.warnings),
        )
        return recall_ctx, None

    def _as_full_context(
        self,
        filtered: list[dict[str, Any]],
        intentions: list[IntentionResponse],
    ) -> RecallContext:
        """Render candidates as the full four-bucket payload. No side effects."""
        identity, decisions, warnings = self._categorize_memories(filtered)
        return RecallContext(
            identity=identity,
            decisions=decisions,
            intentions=intentions,
            warnings=warnings,
            result_mode="full",
        )

    # ── Mid-Session Recall ────────────────────────────────────

    async def mid_session_recall(
        self,
        context: dict[str, Any],
        event: str,
        *,
        index_only: bool = False,
    ) -> list[MemoryResponse] | list[dict[str, Any]]:
        """Lighter recall for mid-session events.

        Triggered by events like ``file_opened`` or ``error_encountered``.
        Returns at most 2 memories to minimize interruption.

        Args:
            context: Current session context dict.
            event: Event type that triggered the recall.
            index_only: Return compact index dicts instead of full memory
                objects. As at session start, nothing is recorded in this
                mode — see the module docstring.

        Returns:
            List of up to 2 relevant MemoryResponse objects, or the same
            number of compact index dicts when *index_only*.
        """
        if self._session_surface_count >= _MAX_SESSION_SURFACES:
            logger.debug("Session surface cap reached, skipping mid-session recall")
            return []

        fingerprint = self._context_builder.build(context)
        logger.debug("Mid-session recall for event=%s", event)

        # Lighter retrieval: fewer candidates
        candidates = await self._retrieve_candidates(fingerprint, limit=20)
        ranked = self._ranker.rank(candidates, current_context=context)
        reranked = self._ranker.rerank(
            ranked,
            max_results=settings.recall_max_during_session,
        )

        filtered = await self._apply_anti_annoyance(reranked)
        capped = filtered[: settings.recall_max_during_session]

        if index_only:
            # Listed, not disclosed: no cooldown, no access recorded.
            return to_index(capped)

        results, surfaced = self._as_responses(capped)
        await self._record_surfacing(surfaced)
        return results

    async def mid_session_recall_measured(
        self,
        context: dict[str, Any],
        event: str,
        *,
        index_only: bool = False,
    ) -> tuple[list[MemoryResponse] | list[dict[str, Any]], list[MemoryResponse] | None]:
        """:meth:`mid_session_recall`, plus the payload index mode replaced.

        Same contract as :meth:`session_start_recall_measured`: the second
        element is the full payload an ``index_only`` call would otherwise
        have returned, rendered from candidates already in memory so the
        comparison costs no extra query and records no surfacing.
        """
        if not index_only:
            return await self.mid_session_recall(context, event), None

        if self._session_surface_count >= _MAX_SESSION_SURFACES:
            logger.debug("Session surface cap reached, skipping mid-session recall")
            return [], []

        fingerprint = self._context_builder.build(context)
        candidates = await self._retrieve_candidates(fingerprint, limit=20)
        ranked = self._ranker.rank(candidates, current_context=context)
        reranked = self._ranker.rerank(
            ranked,
            max_results=settings.recall_max_during_session,
        )
        capped = (await self._apply_anti_annoyance(reranked))[: settings.recall_max_during_session]
        full, _ = self._as_responses(capped)
        return to_index(capped), full

    @staticmethod
    def _as_responses(
        candidates: list[dict[str, Any]],
    ) -> tuple[list[MemoryResponse], list[dict[str, Any]]]:
        """Convert candidates to full responses, dropping unconvertible ones.

        Returns the responses and the candidate dicts that produced them, so
        bookkeeping records exactly what went out.
        """
        results: list[MemoryResponse] = []
        surfaced: list[dict[str, Any]] = []
        for mem_dict in candidates:
            response = _dict_to_memory_response(mem_dict)
            if response:
                results.append(response)
                surfaced.append(mem_dict)
        return results, surfaced

    # ── Dismiss ───────────────────────────────────────────────

    def dismiss(self, memory_id: str, category: str) -> None:
        """Record that the user dismissed a surfaced memory.

        Increments the dismissal counter for the given category
        so future recalls can deprioritize it.

        Args:
            memory_id: UUID string of the dismissed memory.
            category: Category/tag of the dismissed memory.
        """
        self._dismissed_categories[category] += 1
        self._surfaced_memory_ids[memory_id] = datetime.now(UTC)
        logger.debug(
            "Dismissed memory %s (category=%s, total dismissals=%d)",
            memory_id,
            category,
            self._dismissed_categories[category],
        )

    # ── Disclosure bookkeeping ────────────────────────────────

    async def record_disclosure(
        self,
        memory_ids: list[uuid.UUID] | list[str],
        *,
        count_toward_session_cap: bool = False,
    ) -> None:
        """Record that these memories' full content reached a caller.

        This is the single place the two surfacing side effects live: the
        durable 7-day cooldown, and the access count that feeds decay and
        the ``frequency`` ranking signal. It is called by full recall (where
        the response carries the content) and by the expand endpoint
        ``POST /api/v1/memories/batch`` (where an index-mode caller finally
        asks for it). It is deliberately *not* called for an index-only
        recall — see the module docstring.

        Args:
            memory_ids: Ids whose content was delivered.
            count_toward_session_cap: Whether this counts against
                ``_MAX_SESSION_SURFACES``. True for pushed recall, which is
                what the cap exists to limit. False for an expand, which is
                a pull the caller asked for: rate-limiting it would let a
                caller lock itself out of proactive recall by reading its
                own memories.

        Best-effort throughout: bookkeeping must never cost the caller its
        result.
        """
        ids = _as_uuids(memory_ids)
        if not ids:
            return

        now = datetime.now(UTC)
        for mem_id in ids:
            self._surfaced_memory_ids[str(mem_id)] = now
            if count_toward_session_cap:
                self._session_surface_count += 1

        await self._remember_surfaced([str(m) for m in ids])
        await self._record_access(ids)

    # ── Internal Helpers ──────────────────────────────────────

    async def _record_surfacing(self, surfaced: list[dict[str, Any]]) -> None:
        """Record a *full-content* surfacing of these candidate dicts.

        The dict-shaped front door to :meth:`record_disclosure`, used by the
        two recall paths that put content in their response.
        """
        await self.record_disclosure(
            [str(mem.get("id", "")) for mem in surfaced if mem.get("id")],
            count_toward_session_cap=True,
        )

    async def _record_access(self, memory_ids: list[uuid.UUID]) -> None:
        """Count a disclosure as an access on the memories it delivered.

        Nothing did this before, so 916 of 922 memories in the live database
        had access_count = 0 and last_accessed NULL. Decay resolves
        days-since-access from last_accessed and falls back to created_at, so
        it was measuring age rather than disuse and archived every
        non-critical memory 24-51 days after it was written however often it
        had been recalled. The frequency ranking signal was constant for the
        same reason.

        Best-effort: bookkeeping must never cost the caller its recall.
        """
        ids = _as_uuids(memory_ids)
        if not ids:
            return

        try:
            await self._store.touch_many(ids)
        except Exception:
            logger.warning("Failed to record access for %d memories", len(ids), exc_info=True)

    async def _retrieve_candidates(
        self,
        fingerprint: ContextFingerprint,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Query store for active memories matching the context fingerprint."""
        filters: dict[str, Any] = {"status": "active"}

        # Add project filter if available
        if fingerprint.project:
            filters["properties"] = {"project": fingerprint.project}

        # Ranked in SQL by the signals that do not need the fingerprint, not
        # by created_at. list_memories() orders newest-first, which made the
        # pool "the newest N memories" and put everything older permanently
        # out of reach of proactive recall.
        memories = await self._store.list_recall_candidates(
            filters=filters,
            limit=limit,
        )

        # Convert ORM objects to dicts for the ranker
        candidates: list[dict[str, Any]] = []
        for mem in memories:
            cand: dict[str, Any] = {
                "id": str(mem.id),
                "content": mem.content,
                "tags": mem.tags or [],
                "properties": mem.properties or {},
                "importance": mem.importance,
                "trust_score": mem.trust_score,
                "access_count": mem.access_count,
                "last_accessed": mem.last_accessed,
                "created_at": mem.created_at,
                "source_type": mem.source_type,
                "status": mem.status,
                "confidence": mem.confidence,
                "reasoning": mem.reasoning,
                # Provenance and reinforcement. _dict_to_memory_response reads
                # all six; without them it saw None/0 and computed
                # needs_verification as though the memory had never been
                # confirmed — so a fact the user had reinforced repeatedly was
                # still surfaced as unverified.
                "extraction_tier": mem.extraction_tier,
                "extraction_confidence": mem.extraction_confidence,
                "supersedes": mem.supersedes,
                "superseded_by": mem.superseded_by,
                "last_reinforced": mem.last_reinforced,
                "reinforced_count": mem.reinforced_count,
                # Context fields from properties for ranker
                "project": (mem.properties or {}).get("project", ""),
                "module": (mem.properties or {}).get("module", ""),
                "tools": (mem.properties or {}).get("tools", []),
                "files": (mem.properties or {}).get("files", []),
                # Learned usefulness from outcomes. services/impact.py
                # maintains this column, but it was never read into the
                # candidate, so the ranker fell back to its 0.5 default and
                # 0.15 of every score was a constant — the impact
                # subsystem's output was discarded at the one place it is
                # meant to decide anything.
                "impact_score": mem.impact_score,
                # The one deliberate constant. Retrieval here is filter-based,
                # not vector-based, so there is no query embedding to compare
                # against; scoring this properly means embedding the context
                # fingerprint on every recall. Until then 0.20 of the weight
                # is inert, which flattens the spread but does not reorder
                # anything, since a constant shifts every candidate equally.
                "semantic_score": 0.5,
            }
            candidates.append(cand)

        return candidates

    async def _apply_anti_annoyance(
        self,
        candidates: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Filter candidates through anti-annoyance controls."""
        now = datetime.now(UTC)
        filtered: list[dict[str, Any]] = []

        # One round trip for the whole batch, not one per candidate.
        durable_cooldown = await self._on_cooldown(
            [str(c.get("id", "")) for c in candidates if c.get("id")]
        )

        for cand in candidates:
            # Session cap
            if self._session_surface_count + len(filtered) >= _MAX_SESSION_SURFACES:
                break

            mem_id = str(cand.get("id", ""))

            # Cooldown check — durable record first, in-process cache second.
            if mem_id in durable_cooldown:
                continue
            if mem_id in self._surfaced_memory_ids:
                last_surfaced = self._surfaced_memory_ids[mem_id]
                elapsed = (now - last_surfaced).total_seconds()
                if elapsed < _COOLDOWN_SECONDS:
                    continue

            # Dismissed category deprioritization
            tags = cand.get("tags", [])
            if tags:
                primary_tag = tags[0] if isinstance(tags, list) and tags else ""
                if self._dismissed_categories.get(primary_tag, 0) >= 3:
                    continue

            filtered.append(cand)

        return filtered

    def _categorize_memories(
        self,
        candidates: list[dict[str, Any]],
    ) -> tuple[list[MemoryResponse], list[MemoryResponse], list[MemoryResponse]]:
        """Sort memories into identity, decisions, and warnings buckets."""
        identity: list[MemoryResponse] = []
        decisions: list[MemoryResponse] = []
        warnings: list[MemoryResponse] = []

        for cand in candidates:
            response = _dict_to_memory_response(cand)
            if not response:
                continue

            tags = cand.get("tags", []) or []
            source_type = cand.get("source_type", "")

            # Categorize based on tags and source
            if _has_any_tag(tags, {"identity", "preference", "style", "value"}):
                identity.append(response)
            elif _has_any_tag(tags, {"decision", "architecture", "choice"}):
                decisions.append(response)
            elif _has_any_tag(tags, {"warning", "lesson", "bug", "contradiction"}):
                warnings.append(response)
            elif source_type in ("cold_start", "explicit"):
                identity.append(response)
            else:
                decisions.append(response)

        return identity, decisions, warnings

    async def _check_intentions(
        self,
        fingerprint: ContextFingerprint,
    ) -> list[IntentionResponse]:
        """Check for triggered intentions matching the current context."""
        trigger_results = await self._trigger_matcher.check_all(fingerprint)

        intentions: list[IntentionResponse] = []
        for intention in trigger_results.get("time", []):
            intentions.append(IntentionResponse.model_validate(intention))
        for intention in trigger_results.get("context", []):
            intentions.append(IntentionResponse.model_validate(intention))

        return intentions


# ── Module-Level Helpers ──────────────────────────────────────


def _as_uuids(raw_ids: list[uuid.UUID] | list[str]) -> list[uuid.UUID]:
    """Coerce a mixed list of ids to UUIDs, dropping anything unparseable."""
    ids: list[uuid.UUID] = []
    for raw in raw_ids:
        if not raw:
            continue
        try:
            ids.append(raw if isinstance(raw, uuid.UUID) else uuid.UUID(str(raw)))
        except (ValueError, AttributeError, TypeError):
            continue
    return ids


def _dict_to_memory_response(mem_dict: dict[str, Any]) -> MemoryResponse | None:
    """Safely convert a candidate dict to a MemoryResponse.

    Includes provenance (Feature 3) and confidence verification (Feature 4).
    """
    try:
        mem_id = mem_dict.get("id", "")
        if isinstance(mem_id, str):
            mem_id = uuid.UUID(mem_id) if mem_id else uuid.uuid4()

        created_at = mem_dict.get("created_at", datetime.now(UTC))
        confidence = float(mem_dict.get("confidence", 0.5))
        last_reinforced = mem_dict.get("last_reinforced")
        reinforced_count = int(mem_dict.get("reinforced_count", 0))

        # Compute effective confidence decay (Feature 4)
        verify = False
        try:
            from life_graph.scoring.decay import DecayCalculator

            calc = DecayCalculator()
            verify = calc.needs_verification(
                confidence=confidence,
                created_at=created_at,
                last_reinforced=last_reinforced,
                reinforced_count=reinforced_count,
            )
        except Exception:
            pass  # Graceful degradation

        return MemoryResponse(
            id=mem_id,
            content=mem_dict.get("content", ""),
            reasoning=mem_dict.get("reasoning"),
            tags=mem_dict.get("tags"),
            properties=mem_dict.get("properties", {}),
            importance=float(mem_dict.get("importance", 0.5)),
            confidence=confidence,
            source_type=mem_dict.get("source_type", "inferred"),
            created_at=created_at,
            status=mem_dict.get("status", "active"),
            access_count=int(mem_dict.get("access_count", 0)),
            # Provenance (Feature 3)
            extraction_tier=mem_dict.get("extraction_tier"),
            extraction_confidence=mem_dict.get("extraction_confidence"),
            last_accessed=mem_dict.get("last_accessed"),
            supersedes=mem_dict.get("supersedes"),
            superseded_by=mem_dict.get("superseded_by"),
            # Confidence Decay (Feature 4)
            reinforced_count=reinforced_count,
            last_reinforced=last_reinforced,
            needs_verification=verify,
        )
    except (ValueError, TypeError) as exc:
        logger.warning("Failed to convert memory dict to response: %s", exc)
        return None


def _has_any_tag(tags: list[str], target_tags: set[str]) -> bool:
    """Check if any tag in the list matches any target tag."""
    return bool(set(t.lower() for t in tags) & target_tags)

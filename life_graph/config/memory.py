"""The memory engine: embeddings, recall, decay, dedup, capture quality.

One part of :class:`life_graph.config.Settings`; the fields are read as
``LIFE_GRAPH_<NAME>`` like every other setting.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel


class MemorySettings(BaseModel):
    """The memory engine: embeddings, recall, decay, dedup, capture quality."""

    # ── Embeddings ─────────────────────────────────────
    # Modern multilingual local embedder (D6). Dimension is the single source of
    # truth for the pgvector columns (Vector(settings.embedding_dimension)) and
    # the null-and-rebuild migration — keep the two in sync when swapping models.
    # When no embedding backend is reachable the service used to return empty
    # vectors and log a warning, so semantic search silently stopped working
    # while ingestion still reported success. For a memory system that is the
    # wrong failure mode: refuse to start instead. Set false to opt into the
    # degraded mode deliberately (e.g. a keyword-only deployment).
    require_embedding_backend: bool = True
    embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024

    # ── Proactive Recall ───────────────────────────────
    recall_max_session_start: int = 5
    recall_max_during_session: int = 2
    recall_cooldown_days: int = 7
    recall_confidence_threshold: float = 0.7

    # ── Progressive disclosure ─────────────────────────
    # Two halves of the same protocol: an index line names a memory cheaply,
    # then a batch expand fetches the ones that matter.
    #
    # How much of a memory's text a compact index line carries when search or
    # recall is called with index_only. Long enough to recognise a memory,
    # short enough that the line costs ~12 tokens instead of the ~150 a full
    # memory object costs.
    recall_index_content_chars: int = 120
    # Cap on one POST /api/v1/memories/batch expand. Recall hands back at most
    # a few dozen index lines, so a caller with a legitimate reason to expand
    # more than this is really asking for a list endpoint.
    memory_batch_max: int = 50

    # ── Decay ──────────────────────────────────────────
    decay_archive_threshold: float = 0.01
    """Effective-importance floor below which removal is *proposed*.

    A memory's effective importance is ``importance * exp(-decay_rate *
    days_since_activity)``. Falling below this floor makes it a candidate for
    an archive approval -- nothing is archived without one. With the default
    ``memories.decay_rate`` of 0.0217 the horizon is ~180 days since last
    activity for importance 0.5, ~212 days for 1.0. Recall never touches this:
    ranking demotes stale memories on its own recency curve."""

    decay_proposal_limit: int = 50
    # Unreviewed memories older than this are rejected by the nightly decay job
    # (reversible: approve brings one back). 0 = keep waiting forever.
    pending_memory_expiry_days: int = 14
    # A fresh start (ISO timestamp, e.g. 2026-10-23T12:00:00+05:30): day
    # summaries and the capture retry job never read anything older, so
    # archived memories are not written again from old conversations.
    # Empty = no limit.
    memory_start_at: str = ""
    # The local model that decides which searched memories answer a question
    # (services/memory/retrieval.py). Empty = lm_extraction_model, which is
    # also Jarvis's local model here: a separate small judge meant a third
    # model on a 16 GB GPU that holds two, so every personal question
    # reloaded one (~15 s, measured 2026-10-22). The same model, already
    # loaded, judges in ~0.3 s.
    memory_judge_model: str = ""
    # Nothing is forgotten, only further away (services/memory/tiers.py): when
    # no active memory answers, or the question is about the past, archived and
    # replaced memories are searched too, and say so.
    memory_cold_tier: bool = True
    # Memories said together or used together are linked, and a found memory
    # brings its strongest links along for the judge (services/memory/associations.py).
    memory_links: bool = True
    # Search order nudged by how important, used and recent a memory is
    # (services/memory/retrieval.py strength_order).
    memory_strength_rank: bool = False
    # Nightly: active memories without a form slot get one (services/form_fill.py).
    memory_form_fill: bool = True
    # M8 Stage 1 (services/memory/snapshot.py): a personal, local Jarvis turn
    # also builds a read-only context snapshot, time-boxed to 1 s, and keeps
    # its references and labels (no content) in the turn trace. The prompt is
    # unchanged; off means the trace is exactly as before.
    context_snapshot_shadow: bool = False
    # M8 Stage 2 (services/memory/changes.py): with context_snapshot_shadow
    # also on, the turn compares its snapshot with the conversation's previous
    # one and keeps the change list (kinds, references, fixed reasons; no
    # content) in the trace as context_changes. Plain code, no model call,
    # inside the same time box. Off, or with the snapshot flag off, nothing
    # is compared and the trace is exactly as before.
    context_change_shadow: bool = False
    # M8 ingestion ADR §5.3 (services/memory/typed_links.py): the facts of one
    # message get BECAUSE links (from the extractor's reason) and LEADS_TO links
    # (the model's optional leads_to proposal plus a cue word in the text). It
    # also adds the optional leads_to field to the extraction request. No extra
    # model call. Off means the request and the save are exactly as before.
    ingest_typed_links: bool = False
    # M8 decision lifecycle, memory side (services/decision_lifecycle.py, ADR
    # adr-m8-ingestion-structure.md §5.4): a capture ties its candidate
    # decision to the decision memory of the same message; an applied memory
    # supersede supersedes the old memory's *candidate* decision (and the
    # memory undo takes it back); the owner keeping or dropping a linked
    # memory in review confirms or discards the candidate. The owner routes
    # (POST /judgment/decisions/{id}/confirm|discard|review|supersede) are
    # always on. Off: decisions do not follow memories, as before.
    decision_lifecycle: bool = False
    # M8 ingestion step 5 (ADR docs/design/adr-m8-ingestion-structure.md §5.2,
    # services/memory/supersession.py): confidence tiers for a changed fact.
    # High (same slot, the owner's firm words, confidence >= 0.9) applies at
    # once, undoably; a detector hit waits as a contradiction approval; a
    # possible update becomes a review item, at most 5 a day; outside text
    # never makes one. A real world change also ends the old fact's world
    # time (valid_until). Off means the save path behaves exactly as before.
    ingest_supersession_tiers: bool = False
    # One attribute under two slot keys (services/memory/supersession.py
    # slot_pairs): the local model files the same thing under different keys
    # on different days ("my take-home salary is ..." as money.budget, then as
    # work.salary), so the same-slot rule never paired them. With this AND
    # ingest_supersession_tiers on, an active memory of the same subject whose
    # sentence names the same attribute in the same words with a different
    # value ("<attribute> is <value>") is a same-slot pair, tiered like one.
    # Its own flag so the tiers can go on without it. Off: only the same
    # canonical key pairs, as before.
    ingest_slot_pairing: bool = False
    # M8 ingestion step 3 (services/memory/world_time.py, ADR m8-ingestion
    # §5.1): a new memory gets valid_from from its own words ("since 2019",
    # "nethu", "போன மாதம்") by deterministic rules, recorded in
    # properties.world_time, and the extraction call may propose a
    # valid_from that a rule must agree with. Off: saves, the extraction
    # schema and every row are exactly as before.
    ingest_world_time: bool = False
    # M8 world END (services/memory/world_time.py, ADR m8-ingestion §5.1):
    # a new memory gets valid_until from its own words ("until 20 November",
    # "till March", "நவம்பர் 20 வரை", "March varaikum") by deterministic
    # rules, recorded in properties.world_time.end with valid_until_by =
    # "rules". The model's own valid_until is kept only when a rule agrees.
    # Separate from ingest_world_time on purpose: that one is on in prod.
    # Off: the save path stores the extractor's valid_until exactly as before.
    ingest_world_end: bool = False
    # The owner's lasting facts, put in front of every local Jarvis answer
    # whether or not search finds them (services/profile_card.py). 0 = off.
    profile_card_max_items: int = 40
    """Most archive proposals one decay sweep may queue for a tenant.

    Decay proposes rather than archives, so an unbounded first sweep over a
    long-neglected corpus would bury the approval queue. Lowest effective
    importance first, so the clearest candidates surface soonest."""
    decay_default_lambda: float = 0.1

    # ── Deduplication ──────────────────────────────────
    dedup_enabled: bool = True
    dedup_threshold: float = 0.92  # cosine similarity threshold for near-duplicate detection
    # Contradiction check (services/contradiction.py): only active memories at
    # or above this cosine similarity to a new fact are compared with it. Was a
    # hard-coded 0.75 in the module until 2026-10-22.
    contradiction_similarity_threshold: float = 0.75

    # Merge suggestions: nightly, additive. Active pairs whose similarity lands in
    # [merge_review_low, dedup_threshold) coexist today (below the auto-merge line);
    # the producer queues them as merge approvals for the user to confirm.
    merge_review_low: float = 0.85
    merge_suggest_scan_limit: int = 200  # max active memories scanned per tenant per run
    micro_consolidation_dedup: bool = False
    """Let the post-session micro-consolidation supersede near-duplicates.

    Off by default. The step marks a session's *newer* memory superseded when
    an older active one is at cosine >= 0.95, with no LLM check. A negation or
    update ("I no longer use X" next to "I use X") can clear 0.95 with bge-m3,
    so the correction would be hidden behind the stale fact. Off, the step is
    skipped and ``duplicates_removed`` stays 0; ingest-time dedup and the
    nightly merge suggestions are unaffected (audit H8 review, 2026-11-19)."""

    # ── Capture Quality ──────────────────────────────────────
    capture_llm_clean: bool = True  # LLM as primary extractor on the capture path
    extraction_language_guard: bool = True  # skip English NER on non-Latin text
    extraction_tag_only_entities: bool = True  # entities/tech become tags, not memories
    extraction_min_confidence: float = 0.45  # drop facts below this before storing
    # The extractor is told who the people a message names already are, from the
    # people table (extraction/llm.py known_people), instead of guessing.
    extraction_known_people: bool = True
    extraction_llm_min_words: int = 20  # legacy 3-tier LLM gate (non-capture callers)
    extraction_llm_confidence_threshold: float = 0.5  # legacy 3-tier LLM gate

    # Surfaces whose captures are an activity trail, not content: the event row
    # is kept, but extraction, memory storage and the decision/procedure regexes
    # are skipped. Without this, every tool call became several LLM-written
    # "facts" about shell commands, which drowned real memories in the review
    # queue and in recall. Comma-separated; empty string extracts everything.
    # assistant_message too: the assistant's own replies narrate work in hand
    # and produced 3,502 of 3,668 pending memories (2026-10-22). The owner's
    # memory is learnt from the owner's words; the replies stay in the trail.
    capture_no_extract_surfaces: str = "tool_exhaust,assistant_message"
    # Surfaces whose assistant saves explicit "remember that…" requests itself
    # (Jarvis's memory_save): there the extractor drops the facts that the run
    # for the same message already saved (services/saved_by_tool.py).
    capture_saved_by_tool_surfaces: str = "jarvis_app"
    # How long the extractor waits, off the request path, for that run to
    # finish before leaving the capture to the capture sweep.
    capture_saved_by_tool_wait_seconds: int = 90
    # Claude Code sessions (services/claude_code_sessions.py): a session whose
    # SessionEnd marker arrived is closed this long after it, so prompts still
    # being extracted are linked first; one that never sent it (terminal
    # killed, crash) is closed after this long without a new memory.
    claude_code_session_end_grace_minutes: int = 5
    claude_code_session_idle_minutes: int = 240

    # ── Cold Start ─────────────────────────────────────
    cold_start_min_memories: int = 50

    # ── Impact Scoring (Feature 5) ─────────────────────
    impact_boost_on_success: float = 0.1
    impact_penalty_on_failure: float = 0.05
    impact_default: float = 0.5

    def memory_start(self) -> datetime | None:
        """``memory_start_at`` as an aware UTC datetime, or None (unset or unreadable)."""
        if not self.memory_start_at.strip():
            return None
        try:
            at = datetime.fromisoformat(self.memory_start_at.strip())
        except ValueError:
            return None
        return (at if at.tzinfo else at.replace(tzinfo=UTC)).astimezone(UTC)

    @property
    def capture_no_extract_surfaces_list(self) -> list[str]:
        """Surfaces that are logged as capture events but never extracted."""
        return [s.strip() for s in self.capture_no_extract_surfaces.split(",") if s.strip()]

    @property
    def capture_saved_by_tool_surfaces_list(self) -> list[str]:
        """Surfaces whose explicit-save facts are left to the assistant's own tool."""
        return [s.strip() for s in self.capture_saved_by_tool_surfaces.split(",") if s.strip()]

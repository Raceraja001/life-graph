"""Transcript ingestion service — extracts preferences from chat transcripts.

Parses conversation exports from Antigravity, Claude, and ChatGPT,
runs regex-based preference extraction, deduplicates against existing
preferences via cosine similarity, and detects contradictions.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.core.tenant import get_current_tenant_id
from life_graph.models.db import Evidence, Preference
from life_graph.services.embeddings import EmbeddingService

logger = logging.getLogger(__name__)


@dataclass
class ParsedMessage:
    """A single message from a parsed transcript."""

    role: str  # "human" | "assistant"
    content: str


@dataclass
class ExtractedPreference:
    """A preference extracted from transcript text."""

    topic: str
    choice: str
    confidence: float
    pattern: str  # which regex pattern matched
    source_text: str  # original text that matched


@dataclass
class IngestResult:
    """Result of transcript ingestion."""

    preferences_extracted: int = 0
    preferences_reinforced: int = 0
    contradictions_found: int = 0
    processing_time_ms: int = 0
    details: list[dict] = field(default_factory=list)


# ── Extraction Patterns ──────────────────────────────────────

PREFERENCE_PATTERNS = [
    {
        "pattern": re.compile(r"I prefer (\w+) over (\w+)", re.IGNORECASE),
        "type": "preference_over",
        "confidence": 0.8,
    },
    {
        "pattern": re.compile(
            r"I(?:'ve| have) been using (\w+) for (\d+) (?:year|month)s?",
            re.IGNORECASE,
        ),
        "type": "strong_usage",
        "confidence": 0.9,
    },
    {
        "pattern": re.compile(r"I always use (\w+)", re.IGNORECASE),
        "type": "always_use",
        "confidence": 0.85,
    },
    {
        "pattern": re.compile(r"I recommend (\w+)", re.IGNORECASE),
        "type": "recommendation",
        "confidence": 0.7,
    },
    {
        "pattern": re.compile(
            r"(?:my|the) (?:go-to|favorite|preferred) .{0,30}? is (\w+)",
            re.IGNORECASE,
        ),
        "type": "favorite",
        "confidence": 0.85,
    },
]

# Similarity threshold for dedup (cosine)
DEDUP_THRESHOLD = 0.90


class TranscriptExtractor:
    """Extracts preferences from ingested chat transcripts.

    Supports multiple transcript formats (plain text, ChatGPT JSON,
    Claude JSON) and performs deduplication and contradiction detection
    against existing preferences.
    """

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        embedding_service: EmbeddingService,
    ) -> None:
        self._session_factory = session_factory
        self._embedding_service = embedding_service

    # ── Public API ────────────────────────────────────────────

    async def ingest(
        self,
        tenant_id: str,
        messages: list[dict],
        source: str = "antigravity",
        format: str = "plain",
    ) -> IngestResult:
        """Parse transcript, extract preferences, deduplicate, and store.

        Args:
            tenant_id: The tenant performing the ingestion.
            messages: List of {role, content} message dicts.
            source: Origin of the transcript (antigravity, claude, chatgpt).
            format: Format to parse (plain, chatgpt, claude).

        Returns:
            IngestResult with counts and details of extracted preferences.
        """
        t0 = time.monotonic()
        result = IngestResult()

        # Parse messages
        parsed = self._parse_messages(messages, format)

        # Extract preferences from human messages only
        human_text = "\n".join(m.content for m in parsed if m.role == "human")
        if not human_text.strip():
            result.processing_time_ms = int((time.monotonic() - t0) * 1000)
            return result

        extracted = self._extract_preferences(human_text)

        # Process each extracted preference
        for pref in extracted:
            action = await self._process_preference(tenant_id, pref, source)
            result.details.append({
                "topic": pref.topic,
                "choice": pref.choice,
                "confidence": pref.confidence,
                "action": action,
            })
            if action == "created":
                result.preferences_extracted += 1
            elif action == "reinforced":
                result.preferences_reinforced += 1
            elif action == "contradiction":
                result.contradictions_found += 1

        result.processing_time_ms = int((time.monotonic() - t0) * 1000)
        logger.info(
            "Transcript ingestion complete: %d extracted, %d reinforced, %d contradictions (%.0fms)",
            result.preferences_extracted,
            result.preferences_reinforced,
            result.contradictions_found,
            result.processing_time_ms,
        )
        return result

    # ── Parsing ───────────────────────────────────────────────

    def _parse_messages(
        self, messages: list[dict], format: str
    ) -> list[ParsedMessage]:
        """Parse messages based on format type."""
        if format == "chatgpt":
            return self._parse_chatgpt(messages)
        elif format == "claude":
            return self._parse_claude(messages)
        else:  # "plain"
            return self._parse_plain(messages)

    def _parse_plain(self, messages: list[dict]) -> list[ParsedMessage]:
        """Parse plain {role, content} message format.

        Also handles text blocks with Human:/Assistant: prefixes.
        """
        parsed = []
        for msg in messages:
            role = msg.get("role", "human").lower()
            content = msg.get("content", "")

            # Normalize role names
            if role in ("user", "human"):
                role = "human"
            elif role in ("assistant", "ai", "bot"):
                role = "assistant"

            # Check for embedded Human:/Assistant: blocks
            if "\nHuman:" in content or "\nAssistant:" in content:
                blocks = re.split(r"\n(Human|Assistant):\s*", content)
                current_role = role
                for i, block in enumerate(blocks):
                    if block == "Human":
                        current_role = "human"
                    elif block == "Assistant":
                        current_role = "assistant"
                    elif block.strip():
                        parsed.append(ParsedMessage(role=current_role, content=block.strip()))
            else:
                if content.strip():
                    parsed.append(ParsedMessage(role=role, content=content.strip()))

        return parsed

    def _parse_chatgpt(self, messages: list[dict]) -> list[ParsedMessage]:
        """Parse ChatGPT export format (JSON with 'author' field)."""
        parsed = []
        for msg in messages:
            # ChatGPT exports may nest under 'mapping' or 'messages'
            role = msg.get("author", {}).get("role", msg.get("role", "user"))
            content = msg.get("content", {})

            # Content might be a dict with 'parts' or a string
            if isinstance(content, dict):
                parts = content.get("parts", [])
                text = " ".join(str(p) for p in parts if isinstance(p, str))
            elif isinstance(content, str):
                text = content
            else:
                continue

            if role in ("user", "human"):
                role = "human"
            elif role in ("assistant", "ai"):
                role = "assistant"
            else:
                continue  # skip system messages

            if text.strip():
                parsed.append(ParsedMessage(role=role, content=text.strip()))

        return parsed

    def _parse_claude(self, messages: list[dict]) -> list[ParsedMessage]:
        """Parse Claude export format."""
        parsed = []
        for msg in messages:
            role = msg.get("role", msg.get("sender", "human")).lower()
            content = msg.get("content", msg.get("text", ""))

            # Claude may have content as list of dicts with 'text' key
            if isinstance(content, list):
                text = " ".join(
                    item.get("text", "")
                    for item in content
                    if isinstance(item, dict) and item.get("type") == "text"
                )
            elif isinstance(content, str):
                text = content
            else:
                continue

            if role in ("user", "human"):
                role = "human"
            elif role in ("assistant",):
                role = "assistant"
            else:
                continue

            if text.strip():
                parsed.append(ParsedMessage(role=role, content=text.strip()))

        return parsed

    # ── Extraction ────────────────────────────────────────────

    def _extract_preferences(self, text: str) -> list[ExtractedPreference]:
        """Extract preferences from text using regex patterns."""
        results: list[ExtractedPreference] = []
        seen: set[tuple[str, str]] = set()  # (topic, choice) dedup within batch

        for pattern_def in PREFERENCE_PATTERNS:
            pattern = pattern_def["pattern"]
            confidence = pattern_def["confidence"]
            ptype = pattern_def["type"]

            for match in pattern.finditer(text):
                groups = match.groups()

                if ptype == "preference_over":
                    # "I prefer X over Y" → topic derived from Y, choice is X
                    choice, over = groups[0], groups[1]
                    topic = over.lower()
                elif ptype == "strong_usage":
                    # "I've been using X for N years" → strong preference
                    choice = groups[0]
                    duration = int(groups[1])
                    topic = "tool"
                    # Boost confidence for longer usage
                    confidence = min(0.95, confidence + duration * 0.01)
                elif ptype in ("always_use", "recommendation", "favorite"):
                    choice = groups[0]
                    topic = "general"
                else:
                    continue

                key = (topic.lower(), choice.lower())
                if key not in seen:
                    seen.add(key)
                    results.append(ExtractedPreference(
                        topic=topic,
                        choice=choice,
                        confidence=confidence,
                        pattern=ptype,
                        source_text=match.group(0),
                    ))

        return results

    # ── Dedup & Contradiction ─────────────────────────────────

    async def _process_preference(
        self,
        tenant_id: str,
        pref: ExtractedPreference,
        source: str,
    ) -> str:
        """Process a single extracted preference: dedup, contradiction check, store.

        Returns: "created" | "reinforced" | "contradiction" | "skipped"
        """
        # Check for exact match first
        existing = await self._find_existing(tenant_id, pref.topic, pref.choice)
        if existing:
            await self._reinforce(existing, pref)
            return "reinforced"

        # Check for semantic duplicate via embeddings
        dup = await self._dedup_check(tenant_id, pref)
        if dup:
            await self._reinforce(dup, pref)
            return "reinforced"

        # Check for contradiction (same topic, different choice)
        contradiction = await self._detect_contradiction(tenant_id, pref)
        if contradiction:
            # Still create the new preference but mark as contradiction
            await self._create_preference(tenant_id, pref, source)
            return "contradiction"

        # Create new preference
        await self._create_preference(tenant_id, pref, source)
        return "created"

    async def _find_existing(
        self, tenant_id: str, topic: str, choice: str
    ) -> Preference | None:
        """Find an exact topic+choice match."""
        async with self._session_factory() as session:
            stmt = select(Preference).where(
                Preference.tenant_id == tenant_id,
                Preference.status == "active",
                func.lower(Preference.topic) == topic.lower(),
                func.lower(Preference.choice) == choice.lower(),
            )
            return (await session.execute(stmt)).scalar_one_or_none()

    async def _dedup_check(
        self, tenant_id: str, pref: ExtractedPreference
    ) -> Preference | None:
        """Check if a semantically similar preference exists (cosine ≥ 0.90)."""
        try:
            pref_text = f"{pref.topic}: {pref.choice}"
            embedding = self._embedding_service.embed(pref_text)
            if not embedding:
                return None
        except Exception:
            logger.debug("Embedding failed for dedup check, skipping")
            return None

        async with self._session_factory() as session:
            stmt = (
                select(Preference)
                .where(
                    Preference.tenant_id == tenant_id,
                    Preference.status == "active",
                    Preference.embedding.is_not(None),
                )
            )
            rows = (await session.execute(stmt)).scalars().all()

            if not rows:
                return None

            # Compute cosine similarity
            query_vec = np.array(embedding)
            query_norm = np.linalg.norm(query_vec)
            if query_norm == 0:
                return None

            for row in rows:
                row_vec = np.array(row.embedding)
                row_norm = np.linalg.norm(row_vec)
                if row_norm == 0:
                    continue
                sim = np.dot(query_vec, row_vec) / (query_norm * row_norm)
                if sim >= DEDUP_THRESHOLD:
                    logger.debug(
                        "Dedup match: '%s: %s' ≈ '%s: %s' (sim=%.3f)",
                        pref.topic, pref.choice, row.topic, row.choice, sim,
                    )
                    return row

        return None

    async def _detect_contradiction(
        self, tenant_id: str, pref: ExtractedPreference
    ) -> Preference | None:
        """Check if a preference contradicts an existing one (same topic, different choice)."""
        async with self._session_factory() as session:
            stmt = select(Preference).where(
                Preference.tenant_id == tenant_id,
                Preference.status == "active",
                func.lower(Preference.topic) == pref.topic.lower(),
                func.lower(Preference.choice) != pref.choice.lower(),
            )
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if existing:
                logger.info(
                    "Contradiction detected: '%s: %s' vs existing '%s: %s'",
                    pref.topic, pref.choice, existing.topic, existing.choice,
                )
            return existing

    async def _reinforce(
        self, existing: Preference, pref: ExtractedPreference
    ) -> None:
        """Reinforce an existing preference."""
        async with self._session_factory() as session:
            # Merge the detached instance
            existing = await session.merge(existing)
            existing.reinforced_count += 1
            existing.last_reinforced = datetime.now(timezone.utc)
            # Boost confidence slightly
            existing.confidence = min(1.0, existing.confidence + 0.05)

            # Add evidence
            evidence = Evidence(
                tenant_id=existing.tenant_id,
                preference_id=existing.id,
                summary=pref.source_text,
                source_type="transcript",
                stance="supports",
                credibility=pref.confidence,
                properties={"extraction_method": "regex"},
            )
            session.add(evidence)
            await session.commit()
            logger.debug("Reinforced preference %s (count=%d)", existing.id, existing.reinforced_count)

    async def _create_preference(
        self,
        tenant_id: str,
        pref: ExtractedPreference,
        source: str,
    ) -> Preference:
        """Create a new preference with optional embedding."""
        # Generate embedding
        embedding = None
        try:
            pref_text = f"{pref.topic}: {pref.choice}"
            embedding = self._embedding_service.embed(pref_text)
            if not embedding:
                embedding = None
        except Exception:
            logger.debug("Embedding failed for new preference, storing without")

        async with self._session_factory() as session:
            row = Preference(
                tenant_id=tenant_id,
                topic=pref.topic,
                choice=pref.choice,
                confidence=pref.confidence,
                source=source,
                context=pref.source_text,
                embedding=embedding,
            )
            session.add(row)
            await session.flush()

            # Add initial evidence
            evidence = Evidence(
                tenant_id=tenant_id,
                preference_id=row.id,
                summary=pref.source_text,
                source_type="transcript",
                stance="supports",
                credibility=pref.confidence,
                properties={"extraction_method": "regex"},
            )
            session.add(evidence)
            await session.commit()

            logger.info(
                "Created preference: %s → %s (confidence=%.2f, source=%s)",
                pref.topic, pref.choice, pref.confidence, source,
            )
            return row

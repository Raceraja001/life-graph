"""TranscriptDistiller — promote new user-turns from an external AI session into
pending memories and archive the redacted thread to MinIO.

Parallel to ConversationDistiller; reuses MemoryManager.ingest + MinIOStorage.
Progress is tracked by turn index (robust to tools that lack clean timestamps).
"""

from __future__ import annotations

import asyncio
import json
import logging
from types import SimpleNamespace
from typing import Any

from sqlalchemy import select

from life_graph.core.events import EventType, event_bus
from life_graph.core.tenant import get_current_tenant_id
from life_graph.extraction.transcript_extract import extract_transcript_facts
from life_graph.extraction.transcript_parsers.base import Turn
from life_graph.models.db import ExternalSession, _utcnow
from life_graph.models.schemas import MemoryUpdate
from life_graph.services.redaction import redact

logger = logging.getLogger(__name__)

ARCHIVE_BUCKET = "transcripts"

# New turns are extracted with a few preceding turns for context (dedup collapses
# the overlap), so the LLM sees who the user was replying to.
CONTEXT_LOOKBACK = 4


class ExternalSessionNotFoundError(Exception):
    """Raised when the session is missing or owned by another tenant."""


def build_transcript_snapshot(session: Any, turns: list[dict], memory_ids: list) -> bytes:
    """Serialize the redacted thread to a UTF-8 JSON snapshot (bytes)."""
    doc = {
        "tool": session.tool,
        "external_id": session.external_id,
        "tenant_id": session.tenant_id,
        "distilled_at": _utcnow().isoformat(),
        "turns": [{"role": t["role"], "text": redact(t["text"]), "ts": t.get("ts")} for t in turns],
        "distilled_memory_ids": [str(m) for m in memory_ids],
    }
    return json.dumps(doc, ensure_ascii=False, indent=2).encode("utf-8")


class TranscriptDistiller:
    def __init__(
        self, session_factory, memory_manager, minio, store, parsers, resilient_llm
    ) -> None:
        self._session_factory = session_factory
        self._manager = memory_manager
        self._minio = minio
        self._store = store
        self._parsers = parsers
        self._llm = resilient_llm

    async def _load_session(
        self, session, tenant_id: str, external_id: str, *, for_update: bool = False
    ):
        stmt = select(ExternalSession).where(
            ExternalSession.tenant_id == tenant_id,
            ExternalSession.external_id == external_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        rows = await session.execute(stmt)
        return rows.scalars().first()

    async def _advance_marker(self, tenant_id: str, session_id: str, turn_count: int) -> None:
        """Lock the row and move ``last_turn_index`` forward to *turn_count*.

        Never backwards: a concurrent distill that read a longer transcript
        may already have moved it further while this one was extracting.
        """
        async with self._session_factory() as session:
            es = await self._load_session(session, tenant_id, session_id, for_update=True)
            if es is None:  # deleted meanwhile; nothing left to mark
                return
            es.last_turn_index = max(es.last_turn_index or 0, turn_count)
            es.last_distilled_at = _utcnow()
            await session.commit()

    async def distill(self, session_id: str) -> dict:
        """Extract the new user turns of one external session into memories.

        No transaction is held across the slow parts (audit H7): the row is
        read in a short session, the staging object is downloaded, the LLM
        extracts and the archive is uploaded with no session open, and the
        marker is then written under a row lock in a second short session.
        MinIO calls run in a worker thread (audit M19); they are synchronous
        and used to stall the whole event loop.
        """
        tenant_id = get_current_tenant_id()

        async with self._session_factory() as session:
            es = await self._load_session(session, tenant_id, session_id)
            if es is None:
                raise ExternalSessionNotFoundError("External session not found")
            # Plain values: the ORM row is not used once this session closes.
            snap = SimpleNamespace(
                tool=es.tool,
                external_id=es.external_id,
                tenant_id=es.tenant_id,
                raw_key=es.raw_key,
                last_turn_index=es.last_turn_index or 0,
            )

        parser = self._parsers.get(snap.tool)
        if parser is None:
            raise ExternalSessionNotFoundError(f"No parser for tool {snap.tool!r}")

        raw = b""
        if snap.raw_key:
            # Do NOT suppress: a failed read must propagate and abort before the
            # marker is written, so last_turn_index is never regressed to 0.
            # The caller (ARQ job) retries; the marker stays untouched.
            raw = await asyncio.to_thread(self._minio.download, ARCHIVE_BUCKET, snap.raw_key)
        lines = raw.decode("utf-8", errors="replace").splitlines()
        turns = parser.parse(lines)

        new_turns = turns[snap.last_turn_index :]
        new_user_turns = [t for t in new_turns if t["role"] == "user"]

        if not new_user_turns:
            await self._advance_marker(tenant_id, session_id, len(turns))
            return {"new_facts": 0, "archived": False, "skipped": True}

        # Extraction window: new turns + a small lookback for context, redacted.
        start = max(0, snap.last_turn_index - CONTEXT_LOOKBACK)
        window = [
            Turn(role=t["role"], text=redact(t["text"]), ts=t.get("ts")) for t in turns[start:]
        ]
        facts = await extract_transcript_facts(window, resilient_llm=self._llm)
        memories = await self._manager.store_facts(
            facts,
            context={"source_session": session_id, "tool": snap.tool},
            source="transcript",
        )
        for mem in memories:
            tags = list(mem.tags or [])
            changed = False
            for tag in (snap.tool, "transcript"):
                if tag not in tags:
                    tags.append(tag)
                    changed = True
            if changed:
                await self._store.update(mem.id, MemoryUpdate(tags=tags))

        archived = False
        try:
            data = build_transcript_snapshot(snap, turns, [m.id for m in memories])
            key = f"{tenant_id}/{snap.tool}/{session_id}.json"
            await asyncio.to_thread(
                self._minio.upload, ARCHIVE_BUCKET, key, data, content_type="application/json"
            )
            archived = True
        except Exception:  # pragma: no cover - archive must never lose facts
            logger.exception("Transcript archive failed for %s", session_id)

        await self._advance_marker(tenant_id, session_id, len(turns))

        try:
            await event_bus.emit(
                EventType.TRANSCRIPT_DISTILLED,
                {
                    "tool": snap.tool,
                    "external_id": session_id,
                    "tenant_id": tenant_id,
                    "new_facts": len(memories),
                },
                source="transcript_distiller",
            )
        except Exception:
            logger.debug("TRANSCRIPT_DISTILLED emit failed for %s", session_id, exc_info=True)

        return {"new_facts": len(memories), "archived": archived, "skipped": False}

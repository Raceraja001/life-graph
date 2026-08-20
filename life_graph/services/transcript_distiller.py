"""TranscriptDistiller — promote new user-turns from an external AI session into
pending memories and archive the redacted thread to MinIO.

Parallel to ConversationDistiller; reuses MemoryManager.ingest + MinIOStorage.
Progress is tracked by turn index (robust to tools that lack clean timestamps).
"""

from __future__ import annotations

import json
import logging
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

    async def _load_session(self, session, tenant_id: str, external_id: str):
        rows = await session.execute(
            select(ExternalSession).where(
                ExternalSession.tenant_id == tenant_id,
                ExternalSession.external_id == external_id,
            )
        )
        return rows.scalars().first()

    async def distill(self, session_id: str) -> dict:
        tenant_id = get_current_tenant_id()

        async with self._session_factory() as session:
            es = await self._load_session(session, tenant_id, session_id)
            if es is None:
                raise ExternalSessionNotFoundError("External session not found")

            parser = self._parsers.get(es.tool)
            if parser is None:
                raise ExternalSessionNotFoundError(f"No parser for tool {es.tool!r}")

            raw = b""
            if es.raw_key:
                # Do NOT suppress: a failed read must propagate and abort before
                # session.commit() runs, so last_turn_index is never regressed to 0.
                # The caller (ARQ job) retries; the marker stays untouched.
                raw = self._minio.download(ARCHIVE_BUCKET, es.raw_key)
            lines = raw.decode("utf-8", errors="replace").splitlines()
            turns = parser.parse(lines)

            new_turns = turns[es.last_turn_index :]
            new_user_turns = [t for t in new_turns if t["role"] == "user"]

            if not new_user_turns:
                es.last_turn_index = len(turns)
                es.last_distilled_at = _utcnow()
                await session.commit()
                return {"new_facts": 0, "archived": False, "skipped": True}

            # Extraction window: new turns + a small lookback for context, redacted.
            start = max(0, es.last_turn_index - CONTEXT_LOOKBACK)
            window = [
                Turn(role=t["role"], text=redact(t["text"]), ts=t.get("ts")) for t in turns[start:]
            ]
            facts = await extract_transcript_facts(window, resilient_llm=self._llm)
            memories = await self._manager.store_facts(
                facts,
                context={"source_session": session_id, "tool": es.tool},
                source="transcript",
            )
            for mem in memories:
                tags = list(mem.tags or [])
                changed = False
                for tag in (es.tool, "transcript"):
                    if tag not in tags:
                        tags.append(tag)
                        changed = True
                if changed:
                    await self._store.update(mem.id, MemoryUpdate(tags=tags))

            archived = False
            try:
                data = build_transcript_snapshot(es, turns, [m.id for m in memories])
                key = f"{tenant_id}/{es.tool}/{session_id}.json"
                self._minio.upload(ARCHIVE_BUCKET, key, data, content_type="application/json")
                archived = True
            except Exception:  # pragma: no cover - archive must never lose facts
                logger.exception("Transcript archive failed for %s", session_id)

            es.last_turn_index = len(turns)
            es.last_distilled_at = _utcnow()
            await session.commit()

        try:
            await event_bus.emit(
                EventType.TRANSCRIPT_DISTILLED,
                {
                    "tool": es.tool,
                    "external_id": session_id,
                    "tenant_id": tenant_id,
                    "new_facts": len(memories),
                },
                source="transcript_distiller",
            )
        except Exception:
            logger.debug("TRANSCRIPT_DISTILLED emit failed for %s", session_id, exc_info=True)

        return {"new_facts": len(memories), "archived": archived, "skipped": False}

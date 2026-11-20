"""Cross-system sync service — data exchange with external systems.

Handles bidirectional sync with Uzhavu and other systems.
Includes exponential backoff retry logic and memory ingestion.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.core.trust import classify_surface
from life_graph.models.db import CrossSystemSync, Memory, Preference

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

    from life_graph.models.schemas import AnalyticsBatch

logger = logging.getLogger(__name__)

# The capture surface these memories come from (core/trust.py maps it).
SOURCE_TYPE = "uzhavu_sync"


class CrossSystemSyncService:
    """Bidirectional sync with external systems."""

    TIMEOUT = 10  # seconds per request
    MAX_RETRIES = 3
    BACKOFF_DELAYS = [2, 4, 8]  # seconds

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    async def sync_preferences(self, tenant_id: str) -> CrossSystemSync:
        """Sync preferences to Uzhavu — POST with retry logic."""
        import httpx

        async with self._sf() as session:
            prefs = (
                (
                    await session.execute(
                        select(Preference).where(
                            Preference.tenant_id == tenant_id,
                            Preference.status == "active",
                        )
                    )
                )
                .scalars()
                .all()
            )

            payload = {
                "tenant_id": tenant_id,
                "preferences": [
                    {
                        "id": str(p.id),
                        "topic": p.topic,
                        "choice": p.choice,
                        "confidence": p.confidence,
                        "category": p.category,
                    }
                    for p in prefs
                ],
            }

            sync_record = CrossSystemSync(
                tenant_id=tenant_id,
                direction="outbound",
                sync_type="preferences",
                target_system="uzhavu",
                endpoint_url=settings.uzhavu_sync_url,
                request_payload=payload,
                records_sent=len(prefs),
                started_at=datetime.now(UTC),
            )
            session.add(sync_record)
            await session.commit()

            start_ms = time.monotonic()
            last_error = None

            for attempt in range(self.MAX_RETRIES):
                try:
                    async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                        resp = await client.post(
                            settings.uzhavu_sync_url,
                            json=payload,
                            headers={"X-Internal-API-Key": settings.internal_api_key},
                        )
                        resp.raise_for_status()

                    elapsed_ms = int((time.monotonic() - start_ms) * 1000)
                    sync_record.status = "completed"
                    sync_record.records_synced = len(prefs)
                    sync_record.sync_duration_ms = elapsed_ms
                    sync_record.completed_at = datetime.now(UTC)
                    sync_record.response_summary = resp.json() if resp.content else {}
                    await session.commit()

                    await event_bus.emit(
                        EventType.SYNC_COMPLETED,
                        {"sync_id": str(sync_record.id), "records": len(prefs)},
                        source="cross_system_sync",
                    )
                    return sync_record

                except Exception as e:
                    # expected: retried up to MAX_RETRIES; the last error is recorded
                    last_error = str(e)
                    sync_record.retry_count = attempt + 1
                    logger.warning(
                        "Sync attempt %d/%d failed: %s",
                        attempt + 1,
                        self.MAX_RETRIES,
                        e,
                    )
                    if attempt < self.MAX_RETRIES - 1:
                        await asyncio.sleep(self.BACKOFF_DELAYS[attempt])

            # All retries exhausted
            elapsed_ms = int((time.monotonic() - start_ms) * 1000)
            sync_record.status = "failed"
            sync_record.error = last_error
            sync_record.sync_duration_ms = elapsed_ms
            sync_record.completed_at = datetime.now(UTC)
            await session.commit()

            await event_bus.emit(
                EventType.SYNC_FAILED,
                {"sync_id": str(sync_record.id), "error": last_error},
                source="cross_system_sync",
            )
            return sync_record

    async def receive_analytics(
        self,
        tenant_id: str,
        batch: AnalyticsBatch,
    ) -> CrossSystemSync:
        """Receive analytics from Uzhavu and store them as pending memories.

        ``batch`` is validated at the route (importance 0-1, bounded strings,
        at most ANALYTICS_MAX_ITEMS items). Each memory is ``pending`` — it
        goes through the same review queue as every other ingested memory
        instead of being written straight to ``active`` (audit M10) — and is
        inserted in its own SAVEPOINT, so one item the database refuses is
        counted as failed without rolling back the rest of the batch. The old
        per-item try only wrapped ``session.add``, which never touches the
        database, so a bad row failed the whole batch at commit.
        """
        trust_tier = classify_surface(SOURCE_TYPE).value
        async with self._sf() as session:
            sync_record = CrossSystemSync(
                tenant_id=tenant_id,
                direction="inbound",
                sync_type="analytics",
                target_system="uzhavu",
                request_payload=batch.model_dump(mode="json"),
                records_sent=len(batch.items),
                started_at=datetime.now(UTC),
            )
            session.add(sync_record)
            await session.flush()

            stored: list[dict[str, str]] = []
            failed = 0
            for item in batch.items:
                memory = Memory(
                    tenant_id=tenant_id,
                    content=item.content,
                    content_hash=hashlib.sha256(item.content.strip().lower().encode()).hexdigest(),
                    source_type=SOURCE_TYPE,
                    source=item.source,
                    importance=item.importance,
                    properties=item.properties,
                    tags=item.tags,
                    status="pending",
                    trust_tier=trust_tier,
                )
                try:
                    async with session.begin_nested():
                        session.add(memory)
                except SQLAlchemyError:
                    failed += 1
                    logger.warning("Failed to ingest analytics item", exc_info=True)
                else:
                    # id is assigned by the flush on leaving the savepoint;
                    # read it now rather than off a row after commit.
                    stored.append(
                        {
                            "id": str(memory.id),
                            "source_type": SOURCE_TYPE,
                            "preview": item.content[:80],
                            "tenant_id": tenant_id,
                        }
                    )

            sync_record.status = "completed"
            sync_record.records_synced = len(stored)
            sync_record.records_failed = failed
            sync_record.completed_at = datetime.now(UTC)
            await session.commit()
            await session.refresh(sync_record)

            await self._announce_pending(stored)
            synced = len(stored)

            await event_bus.emit(
                EventType.SYNC_COMPLETED,
                {
                    "sync_id": str(sync_record.id),
                    "synced": synced,
                    "failed": failed,
                },
                source="cross_system_sync",
            )
            return sync_record

    @staticmethod
    async def _announce_pending(stored: list[dict[str, str]]) -> None:
        """MEMORY_PENDING per stored memory, as PostgresMemoryStore.store() emits,
        so these reach the review queue's notifications like any other."""
        for payload in stored:
            try:
                await event_bus.emit(EventType.MEMORY_PENDING, payload, source="cross_system_sync")
            except Exception:  # events must never break the sync
                logger.warning("MEMORY_PENDING emit failed", exc_info=True)

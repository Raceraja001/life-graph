"""Cross-system sync service — data exchange with external systems.

Handles bidirectional sync with Uzhavu and other systems.
Includes exponential backoff retry logic and memory ingestion.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from life_graph.config import settings
from life_graph.core.events import EventType, event_bus
from life_graph.models.db import CrossSystemSync, Memory, Preference

logger = logging.getLogger(__name__)


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
                await session.execute(
                    select(Preference).where(
                        Preference.tenant_id == tenant_id,
                        Preference.status == "active",
                    )
                )
            ).scalars().all()

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
                started_at=datetime.now(timezone.utc),
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
                    sync_record.completed_at = datetime.now(timezone.utc)
                    sync_record.response_summary = (
                        resp.json() if resp.content else {}
                    )
                    await session.commit()

                    await event_bus.emit(
                        EventType.SYNC_COMPLETED,
                        {"sync_id": str(sync_record.id), "records": len(prefs)},
                        source="cross_system_sync",
                    )
                    return sync_record

                except Exception as e:
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
            sync_record.completed_at = datetime.now(timezone.utc)
            await session.commit()

            await event_bus.emit(
                EventType.SYNC_FAILED,
                {"sync_id": str(sync_record.id), "error": last_error},
                source="cross_system_sync",
            )
            return sync_record

    async def receive_analytics(
        self, tenant_id: str, data: dict,
    ) -> CrossSystemSync:
        """Receive analytics from Uzhavu and store as memories."""
        async with self._sf() as session:
            sync_record = CrossSystemSync(
                tenant_id=tenant_id,
                direction="inbound",
                sync_type="analytics",
                target_system="uzhavu",
                request_payload=data,
                records_sent=len(data.get("items", [])),
                started_at=datetime.now(timezone.utc),
            )
            session.add(sync_record)

            synced = 0
            failed = 0
            for item in data.get("items", []):
                try:
                    memory = Memory(
                        tenant_id=tenant_id,
                        content=item.get("content", ""),
                        source_type="uzhavu_sync",
                        source=item.get("source", "uzhavu"),
                        importance=item.get("importance", 0.5),
                        properties=item.get("properties", {}),
                        tags=item.get("tags"),
                    )
                    session.add(memory)
                    synced += 1
                except Exception:
                    failed += 1
                    logger.warning(
                        "Failed to ingest analytics item", exc_info=True,
                    )

            sync_record.status = "completed"
            sync_record.records_synced = synced
            sync_record.records_failed = failed
            sync_record.completed_at = datetime.now(timezone.utc)
            await session.commit()
            await session.refresh(sync_record)

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

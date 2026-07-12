"""Capture Spine — universal input layer.

Append-only ingress for all surfaces. Every piece of information
enters through here, gets deduped, and fans out via EventBus.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.core.events import EventBus, EventType
from life_graph.models.db import CaptureEvent, Correction
from life_graph.storage.database import async_session


class CaptureService:
    """Manages capture event ingestion, dedup, corrections, and queries.

    Operates on a caller-provided ``AsyncSession`` — the API layer
    is responsible for committing the transaction after the service
    method returns.
    """

    def __init__(self, session: AsyncSession, event_bus: EventBus | None = None):
        self.session = session
        self.event_bus = event_bus

    # ── Ingest ────────────────────────────────────────────────

    async def ingest(
        self,
        tenant_id: str,
        surface: str,
        content: str,
        modality: str = "text",
        occurred_at: datetime | None = None,
        properties: dict | None = None,
    ) -> CaptureEvent:
        """Universal capture ingress with SHA-256 dedup (10-min window per surface).

        If the same content hash + surface is found within the last 10 minutes,
        the existing event is marked as ``duplicate`` and returned instead.

        Args:
            tenant_id: Tenant scope.
            surface: Source surface identifier.
            content: Raw content string.
            modality: Content modality (text, voice, image, structured).
            occurred_at: Explicit timestamp; defaults to UTC now.
            properties: Arbitrary JSONB metadata.

        Returns:
            The new or duplicate ``CaptureEvent``.
        """
        now = occurred_at or datetime.now(timezone.utc)
        content_hash = hashlib.sha256(content.encode()).hexdigest()

        # Dedup: same hash + same surface within 10 minutes
        window = now - timedelta(minutes=10)
        existing = await self.session.execute(
            select(CaptureEvent).where(
                CaptureEvent.tenant_id == tenant_id,
                CaptureEvent.content_hash == content_hash,
                CaptureEvent.surface == surface,
                CaptureEvent.occurred_at >= window,
            )
        )
        if dup := existing.scalars().first():
            dup.status = "duplicate"
            return dup

        event = CaptureEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            surface=surface,
            modality=modality,
            content=content,
            content_hash=content_hash,
            status="received",
            yield_count=0,
            occurred_at=now,
            properties=properties or {},
        )
        self.session.add(event)
        await self.session.flush()

        if self.event_bus:
            await self.event_bus.emit(
                EventType.CAPTURE_RECEIVED,
                {
                    "capture_event_id": str(event.id),
                    "tenant_id": tenant_id,
                    "surface": surface,
                    "modality": modality,
                },
            )
        return event

    # ── Corrections ───────────────────────────────────────────

    async def record_correction(
        self,
        tenant_id: str,
        kind: str,
        original: str | None = None,
        corrected: str | None = None,
        capture_event_id: uuid.UUID | None = None,
        diff_summary: str | None = None,
        context: dict | None = None,
        domain_tags: list[str] | None = None,
    ) -> Correction:
        """Record a user correction (edit, override, reject, approve).

        Args:
            tenant_id: Tenant scope.
            kind: Correction type (edit, override, reject, approve).
            original: Original text before correction.
            corrected: Corrected text.
            capture_event_id: Optional link to the originating capture event.
            diff_summary: Human-readable diff description.
            context: Arbitrary context metadata.
            domain_tags: Tags for the correction domain.

        Returns:
            The persisted ``Correction`` row.
        """
        correction = Correction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            capture_event_id=capture_event_id,
            kind=kind,
            original=original,
            corrected=corrected,
            diff_summary=diff_summary,
            context=context or {},
            domain_tags=domain_tags or [],
        )
        self.session.add(correction)
        await self.session.flush()

        if self.event_bus:
            await self.event_bus.emit(
                EventType.CORRECTION_RECORDED,
                {
                    "correction_id": str(correction.id),
                    "tenant_id": tenant_id,
                    "kind": kind,
                },
            )
        return correction

    # ── Queries ───────────────────────────────────────────────

    async def list_events(
        self,
        tenant_id: str,
        surface: str | None = None,
        since: datetime | None = None,
        limit: int = 50,
    ) -> list[CaptureEvent]:
        """List capture events, optionally filtered by surface and time.

        Args:
            tenant_id: Tenant scope.
            surface: Filter by source surface.
            since: Only events after this timestamp.
            limit: Maximum rows to return.

        Returns:
            List of ``CaptureEvent`` rows, newest first.
        """
        stmt = (
            select(CaptureEvent)
            .where(CaptureEvent.tenant_id == tenant_id)
            .order_by(CaptureEvent.occurred_at.desc())
            .limit(limit)
        )
        if surface:
            stmt = stmt.where(CaptureEvent.surface == surface)
        if since:
            stmt = stmt.where(CaptureEvent.occurred_at >= since)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_corrections(
        self,
        tenant_id: str,
        kind: str | None = None,
        limit: int = 50,
    ) -> list[Correction]:
        """List corrections, optionally filtered by kind.

        Args:
            tenant_id: Tenant scope.
            kind: Filter by correction kind (edit, override, etc.).
            limit: Maximum rows to return.

        Returns:
            List of ``Correction`` rows, newest first.
        """
        stmt = (
            select(Correction)
            .where(Correction.tenant_id == tenant_id)
            .order_by(Correction.created_at.desc())
            .limit(limit)
        )
        if kind:
            stmt = stmt.where(Correction.kind == kind)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    # ── Correction Export (you-model training triples) ────────

    @staticmethod
    def to_triple(correction: Correction) -> dict:
        """Shape a correction into an ``(original, corrected, context)`` triple.

        Args:
            correction: A ``Correction`` row (or duck-typed equivalent).

        Returns:
            Dict with original/corrected/context/domain_tags/kind/created_at.
        """
        return {
            "original": correction.original,
            "corrected": correction.corrected,
            "context": correction.context or {},
            "domain_tags": correction.domain_tags or [],
            "kind": correction.kind,
            "created_at": (
                correction.created_at.isoformat()
                if correction.created_at
                else None
            ),
        }

    @staticmethod
    def is_exportable(correction: Correction) -> bool:
        """Whether a correction may appear in the training-triple export.

        A usable triple needs both sides present. Corrections may opt out
        of export by setting ``context.exportable = False`` (sensitive
        drafts) — see capture-spine spec privacy note.
        """
        if (correction.context or {}).get("exportable") is False:
            return False
        return bool(correction.original) and bool(correction.corrected)

    @classmethod
    async def stream_export_triples(
        cls,
        tenant_id: str,
        *,
        session_factory=None,
    ):
        """Async-generate exportable correction triples for a tenant.

        Opens its own session (so it is safe to consume inside a
        ``StreamingResponse`` after the request handler returns) and
        streams rows oldest-first without buffering the full table.

        Args:
            tenant_id: Tenant scope.
            session_factory: Session factory; defaults to ``async_session``.

        Yields:
            Triple dicts (see :meth:`to_triple`).
        """
        factory = session_factory or async_session
        async with factory() as session:
            result = await session.stream_scalars(
                select(Correction)
                .where(Correction.tenant_id == tenant_id)
                .order_by(Correction.created_at.asc(), Correction.id.asc())
            )
            async for correction in result:
                if cls.is_exportable(correction):
                    yield cls.to_triple(correction)

    # ── Yield Tracking ────────────────────────────────────────

    async def update_yield_count(
        self, capture_event_id: uuid.UUID, delta: int = 1
    ) -> None:
        """Increment yield_count after processing produces artifacts.

        Args:
            capture_event_id: The capture event to update.
            delta: How much to increment (default 1).
        """
        result = await self.session.execute(
            select(CaptureEvent).where(CaptureEvent.id == capture_event_id)
        )
        if event := result.scalars().first():
            event.yield_count = (event.yield_count or 0) + delta
            event.status = "processed"

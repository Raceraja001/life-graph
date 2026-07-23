"""Background job: run the slow half of multi-modal capture ingestion.

``life_graph.api.multimodal`` (voice/image/document endpoints) does only
the fast, synchronous part of a capture inline — MinIO upload plus
transcription/OCR/PDF-extraction and the empty-text validation — then
enqueues this job to do the rest: extraction → scoring → dedup →
embedding → storage, via ``MemoryManager.ingest`` (with the same
raw-text fallback used everywhere else when zero facts are extracted).

The worker process has no request-scoped tenant contextvar, so the
tenant is passed explicitly and the contextvar is set here before
touching ``MemoryManager`` — same pattern as
``life_graph.workers.tasks.run_tenant_consolidation``.

The domain event (``voice:transcribed`` / ``image:processed`` /
``document:imported``) is emitted from here too, once, on completion —
not from the request-time endpoint, since the real memory count isn't
known until ingestion actually runs. This mirrors how
``life_graph.workers.tasks.run_watchers`` emits ``WATCHER_COMPLETED``
from inside the worker job: ``event_bus.emit(...)`` bridges to Redis for
cross-instance fan-out to webhook/WebSocket subscribers regardless of
which process (API or worker) emits it.

Entry point:
    - ``ingest_capture_text``: ARQ task, one job per capture. For
      documents (multiple chunks), the chunking loop runs *inside* this
      job (over the full extracted text) so ordering and dedup for a
      single capture stay in one place, rather than being split across
      several enqueued jobs.
"""

from __future__ import annotations

import logging
from typing import Any

from life_graph.core.tenant import set_tenant_context
from life_graph.services.multimodal import ingest_or_fallback, split_into_chunks

logger = logging.getLogger(__name__)

# source -> (EventType attribute name, length-field name in the payload)
_EVENT_BY_SOURCE = {
    "voice": ("VOICE_TRANSCRIBED", "transcript_length"),
    "image": ("IMAGE_PROCESSED", "ocr_text_length"),
    "document": ("DOCUMENT_IMPORTED", "text_length"),
}


async def ingest_capture_text(
    ctx: dict, text: str, source: str, tenant_id: str, meta: dict[str, Any] | None = None
) -> int:
    """ARQ task: ingest queued capture text for one tenant.

    Args:
        ctx: ARQ context (contains ``redis`` connection; unused here).
        text: The extracted text (transcript / OCR text / full document
            text). For ``source == "document"`` this may be split into
            multiple chunks internally.
        source: One of ``"voice"``, ``"image"``, ``"document"`` — passed
            through to ``MemoryManager.ingest`` / the raw-text fallback,
            and used to pick which domain event to emit.
        tenant_id: The owning tenant. The request's tenant contextvar
            does not cross the process boundary into the worker, so it
            is set explicitly here before any storage access.
        meta: Extra fields carried from the request for the event
            payload — ``filename`` and ``minio_key`` (whatever the old
            synchronous emit included besides the memory count, which
            is only known here).

    Returns:
        Total number of memories created (across all chunks, for
        documents).
    """
    set_tenant_context(tenant_id, "system")

    from life_graph.api.dependencies import get_memory_manager

    manager = get_memory_manager()

    # Documents may be long enough to need chunking; voice/image capture
    # is always a single chunk. Keeping the loop here (rather than
    # enqueuing one job per chunk) keeps ordering and dedup for a single
    # capture in one place.
    chunks = split_into_chunks(text) if source == "document" else [text]

    total = 0
    for chunk in chunks:
        memories = await ingest_or_fallback(manager, chunk, source)
        total += len(memories)

    logger.info(
        "Ingested capture for tenant %s (source=%s): %d chunk(s), %d memories",
        tenant_id, source, len(chunks), total,
    )

    event_info = _EVENT_BY_SOURCE.get(source)
    if event_info is not None:
        from life_graph.core.events import EventType, event_bus

        event_type_name, length_field = event_info
        meta = meta or {}
        payload: dict[str, Any] = {
            "filename": meta.get("filename"),
            "minio_key": meta.get("minio_key"),
            length_field: len(text),
            "memories_created": total,
        }
        if source == "document":
            payload["chunks"] = len(chunks)
        await event_bus.emit(
            getattr(EventType, event_type_name), payload, source="multimodal"
        )

    return total

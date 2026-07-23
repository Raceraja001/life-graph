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

Entry point:
    - ``ingest_capture_text``: ARQ task, one job per capture. For
      documents (multiple chunks), the chunking loop runs *inside* this
      job (over the full extracted text) so ordering and dedup for a
      single capture stay in one place, rather than being split across
      several enqueued jobs.
"""

from __future__ import annotations

import logging

from life_graph.core.tenant import set_tenant_context
from life_graph.services.multimodal import ingest_or_fallback, split_into_chunks

logger = logging.getLogger(__name__)


async def ingest_capture_text(ctx: dict, text: str, source: str, tenant_id: str) -> int:
    """ARQ task: ingest queued capture text for one tenant.

    Args:
        ctx: ARQ context (contains ``redis`` connection; unused here).
        text: The extracted text (transcript / OCR text / full document
            text). For ``source == "document"`` this may be split into
            multiple chunks internally.
        source: One of ``"voice"``, ``"image"``, ``"document"`` — passed
            through to ``MemoryManager.ingest`` / the raw-text fallback.
        tenant_id: The owning tenant. The request's tenant contextvar
            does not cross the process boundary into the worker, so it
            is set explicitly here before any storage access.

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
    return total

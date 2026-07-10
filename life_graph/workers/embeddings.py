"""Background job for batch embedding generation.

Used by the bulk import flow to make imported memories searchable
without blocking the import HTTP request.  Processes memory IDs in
configurable chunks (default 32) and records progress via the
:class:`JobRun` model.

Entry point:
    - ``generate_embeddings_batch``: ARQ task that embeds a list of
      memory IDs for a single tenant.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update

from life_graph.config import settings
from life_graph.models.db import JobRun, Memory
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

BATCH_SIZE: int = 32
"""Number of memories to embed in a single database transaction."""


async def generate_embeddings_batch(
    ctx: dict,
    memory_ids: list[str],
    tenant_id: str,
) -> dict:
    """ARQ task: generate embeddings for a batch of memories.

    Loads memories by ID, calls the embedding service for each, and
    persists the resulting vectors.  Processes in chunks of
    ``BATCH_SIZE`` to keep individual transactions short.

    Job execution is tracked via a :class:`JobRun` record.

    Args:
        ctx: ARQ context (contains ``redis`` connection).
        memory_ids: List of memory UUID strings to embed.
        tenant_id: The owning tenant (used for job tracking).

    Returns:
        Dict with ``processed``, ``failed``, and ``total`` counts.

    Raises:
        Exception: Re-raised after marking the job as failed so ARQ retries.
    """
    from life_graph.services.embedding import get_embedding_service

    # Create job record
    job_id = uuid.uuid4()
    async with async_session() as session:
        job = JobRun(
            id=job_id,
            tenant_id=tenant_id,
            job_name="generate_embeddings",
            status="running",
            started_at=datetime.now(timezone.utc),
        )
        session.add(job)
        await session.commit()

    try:
        embedding_service = get_embedding_service()
        processed = 0
        failed = 0

        # Process in chunks to keep transactions short
        for i in range(0, len(memory_ids), BATCH_SIZE):
            chunk_ids = memory_ids[i : i + BATCH_SIZE]

            async with async_session() as session:
                result = await session.execute(
                    select(Memory).where(Memory.id.in_(chunk_ids))
                )
                memories = result.scalars().all()

                for memory in memories:
                    try:
                        embedding = await embedding_service.embed(memory.content)
                        memory.embedding = embedding

                        # Use the correct model name based on configuration
                        if settings.use_local_llm:
                            memory.embedding_model = settings.lm_embedding_model
                        else:
                            memory.embedding_model = settings.embedding_model

                        processed += 1
                    except Exception as exc:
                        logger.warning(
                            "Failed to embed memory %s: %s",
                            memory.id,
                            exc,
                        )
                        failed += 1

                await session.commit()

            logger.debug(
                "Embedding chunk %d-%d complete (%d processed, %d failed so far)",
                i,
                min(i + BATCH_SIZE, len(memory_ids)),
                processed,
                failed,
            )

        result_data = {
            "processed": processed,
            "failed": failed,
            "total": len(memory_ids),
        }

        # Update job as success
        async with async_session() as session:
            await session.execute(
                update(JobRun)
                .where(JobRun.id == job_id)
                .values(
                    status="success",
                    completed_at=datetime.now(timezone.utc),
                    result=result_data,
                )
            )
            await session.commit()

        logger.info(
            "Embedding batch complete: %d processed, %d failed out of %d total",
            processed,
            failed,
            len(memory_ids),
        )
        return result_data

    except Exception as exc:
        # Mark job as failed
        async with async_session() as session:
            await session.execute(
                update(JobRun)
                .where(JobRun.id == job_id)
                .values(
                    status="failed",
                    completed_at=datetime.now(timezone.utc),
                    error=str(exc),
                )
            )
            await session.commit()

        logger.exception("Embedding batch failed for tenant %s", tenant_id)
        raise

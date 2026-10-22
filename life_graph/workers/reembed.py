"""Versioned re-embed job — regenerate embeddings after a model/dimension change.

After migration ``025`` clears and re-dimensions the pgvector columns, this job
repopulates them with the configured model (``current_embedding_model()``). It is
generic over the 8 embedded tables, idempotent, and resumable: each run only
touches rows that still need embedding (``embedding IS NULL``) plus, for tables
that version their embedder, rows whose ``embedding_model`` is stale.

Local inference is zero-API-cost, so this job is NOT gated by the Governor.

Entry points:
    - ``reembed_table``: re-embed one table for all tenants.
    - ``reembed_all``: re-embed every registered table (ARQ task + CLI).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy import or_, select

from life_graph.models.db import (
    Decision,
    Evidence,
    Intention,
    KnowledgeGap,
    Memory,
    Preference,
    Session,
    SharedContext,
)
from life_graph.services.embeddings import current_embedding_model
from life_graph.storage.database import async_session

logger = logging.getLogger(__name__)

BATCH_SIZE = 64


@dataclass(frozen=True)
class _EmbedTarget:
    """A table to re-embed: which model, which text column, versioned or not."""

    model: type
    text_attr: str
    versioned: bool  # has an embedding_model column


# The 8 embedded tables. ``text_attr`` is the field embedded for search.
REGISTRY: list[_EmbedTarget] = [
    _EmbedTarget(Memory, "content", versioned=True),
    _EmbedTarget(Preference, "topic", versioned=True),
    _EmbedTarget(Evidence, "summary", versioned=True),
    _EmbedTarget(Session, "summary", versioned=False),
    _EmbedTarget(Intention, "content", versioned=False),
    _EmbedTarget(KnowledgeGap, "topic", versioned=False),
    _EmbedTarget(SharedContext, "content", versioned=False),
    _EmbedTarget(Decision, "title", versioned=False),
]


def _needs_embedding_clause(target: _EmbedTarget, model_name: str):
    """Rows that still need (re-)embedding for this target.

    ``model_name`` must be :func:`current_embedding_model` — the same name
    ingest stamps. This compared against ``settings.embedding_model`` while
    local-LLM ingest stamped ``settings.lm_embedding_model``, so every locally
    embedded row looked stale forever (code review, 2026-10-22).
    """
    model = target.model
    null_embedding = model.embedding.is_(None)
    if target.versioned:
        return or_(
            null_embedding,
            model.embedding_model != model_name,
        )
    return null_embedding


async def reembed_table(target: _EmbedTarget, *, batch_size: int = BATCH_SIZE) -> dict:
    """Re-embed one table in batches. Returns {processed, failed}.

    Terminates on two guards. Rows that fail are excluded from later batches,
    so the loop cannot keep re-selecting the same unembeddable rows; and a
    batch that embeds nothing stops the run (the embedder is down). The old
    guard compared the *cumulative* processed count, so once any batch had
    succeeded, rows that could never be embedded looped forever (code review,
    2026-10-22).

    Vectors come from ``embed_batch_async`` — the same backend ingest uses
    (the LM client in local-LLM mode). The sync ``embed_batch`` always used
    sentence-transformers, so a "re-embed" could fill the column with vectors
    from a different model than the one search queries with.
    """
    from life_graph.api.dependencies import get_embedding_service

    service = get_embedding_service()
    model = target.model
    model_name = current_embedding_model()
    processed = 0
    failed = 0
    failed_ids: set = set()

    while True:
        stmt = select(model).where(_needs_embedding_clause(target, model_name))
        if failed_ids:
            stmt = stmt.where(model.id.notin_(failed_ids))
        async with async_session() as session:
            rows = (await session.execute(stmt.limit(batch_size))).scalars().all()
            if not rows:
                break

            texts = [(getattr(r, target.text_attr) or "") for r in rows]
            vectors = await service.embed_batch_async(texts, batch_size=batch_size)

            batch_processed = 0
            for row, vector in zip(rows, vectors, strict=False):
                if not vector:  # embedder unavailable / empty text
                    failed += 1
                    failed_ids.add(row.id)
                    continue
                row.embedding = vector
                if target.versioned:
                    row.embedding_model = model_name
                batch_processed += 1
            processed += batch_processed
            await session.commit()

        logger.info(
            "Re-embedded %s: %d done, %d failed so far",
            model.__tablename__,
            processed,
            failed,
        )
        if batch_processed == 0:
            logger.warning(
                "Re-embed of %s made no progress this batch (embedder unavailable?) — stopping",
                model.__tablename__,
            )
            break

    return {"table": model.__tablename__, "processed": processed, "failed": failed}


async def reembed_all(ctx: dict | None = None, *, batch_size: int = BATCH_SIZE) -> dict:
    """Re-embed every registered table. ARQ task signature (``ctx``) + CLI entry."""
    results = []
    for target in REGISTRY:
        results.append(await reembed_table(target, batch_size=batch_size))
    total = sum(r["processed"] for r in results)
    logger.info("Re-embed complete: %d rows across %d tables", total, len(results))
    return {"model": current_embedding_model(), "total": total, "tables": results}

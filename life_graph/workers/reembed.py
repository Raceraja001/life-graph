"""Versioned re-embed job — regenerate embeddings after a model/dimension change.

After migration ``025`` clears and re-dimensions the pgvector columns, this job
repopulates them with the configured model (``settings.embedding_model``). It is
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

from life_graph.config import settings
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


def _needs_embedding_clause(target: _EmbedTarget):
    """Rows that still need (re-)embedding for this target."""
    model = target.model
    null_embedding = model.embedding.is_(None)
    if target.versioned:
        return or_(
            null_embedding,
            model.embedding_model != settings.embedding_model,
        )
    return null_embedding


async def reembed_table(target: _EmbedTarget, *, batch_size: int = BATCH_SIZE) -> dict:
    """Re-embed one table in batches. Returns {processed, failed}."""
    from life_graph.api.dependencies import get_embedding_service

    service = get_embedding_service()
    model = target.model
    processed = 0
    failed = 0

    while True:
        async with async_session() as session:
            rows = (
                await session.execute(
                    select(model)
                    .where(_needs_embedding_clause(target))
                    .limit(batch_size)
                )
            ).scalars().all()
            if not rows:
                break

            texts = [(getattr(r, target.text_attr) or "") for r in rows]
            vectors = service.embed_batch(texts, batch_size=batch_size)

            for row, vector in zip(rows, vectors, strict=False):
                if not vector:  # embedder unavailable / empty text
                    failed += 1
                    continue
                row.embedding = vector
                if target.versioned:
                    row.embedding_model = settings.embedding_model
                processed += 1
            await session.commit()

        logger.info(
            "Re-embedded %s: %d done, %d failed so far",
            model.__tablename__, processed, failed,
        )
        # Safety: if a whole batch failed (no progress possible), stop to avoid
        # an infinite loop on rows that can never be embedded.
        if processed == 0 and failed >= batch_size:
            logger.warning(
                "Re-embed of %s made no progress (embedder unavailable?) — stopping",
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
    return {"model": settings.embedding_model, "total": total, "tables": results}

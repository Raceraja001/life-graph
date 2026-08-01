"""One-time memory cleanup — queues fragment/duplicate memories for merge.

Scans a tenant's active memories for same-utterance fragments/duplicates:
pairs whose cosine similarity lands in the review band
``[merge_review_low, dedup_threshold)`` (mirrors ``services.merge_suggestions``'
near-dup band) OR pairs whose ``properties.entities`` overlap — the latter
catches duplicates that already crept past the auto-merge line (>= dedup_threshold)
and still coexist as two active memories. For each qualifying pair, queues a
``kind='merge'`` Approval with ``source='cleanup'`` so resolution reuses the
existing merge-approval mechanics (``ApprovalService._apply_merge``).

This job never deletes or rewrites memories itself — it only queues
approvals for human review. It is a one-time backfill (not on the nightly
cron); trigger it via ``POST /admin/jobs/cleanup-memories``.

Idempotent: ``source_ref`` is a stable hash of the sorted memory-id pair, so
re-running after pairs have been approved/rejected does not re-queue them
(mirrors ``services.merge_suggestions.MergeSuggestionService.scan_and_queue``,
but keyed on ``source='cleanup'`` so the two producers never collide).
"""

from __future__ import annotations

import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.config import settings
from life_graph.core.tenant import set_tenant_context
from life_graph.models.db import Approval, Memory
from life_graph.storage.database import async_session
from life_graph.storage.postgres import PostgresMemoryStore

logger = logging.getLogger(__name__)


def _pair_ref(id_a: str, id_b: str) -> str:
    """Stable, order-independent hash of a memory pair, used as source_ref."""
    joined = "|".join(sorted((str(id_a), str(id_b))))
    return hashlib.sha256(joined.encode()).hexdigest()


async def _cleanup_tenant(session: AsyncSession, store: PostgresMemoryStore, tenant_id: str) -> int:
    """Queue merge approvals for fragment/duplicate memory pairs. Returns count queued."""
    low = settings.merge_review_low
    high = settings.dedup_threshold

    # Pairs already queued/resolved by this producer — skip them.
    seen: set[str] = set(
        (
            await session.execute(
                select(Approval.source_ref).where(
                    Approval.tenant_id == tenant_id,
                    Approval.source == "cleanup",
                    Approval.source_ref.is_not(None),
                )
            )
        )
        .scalars()
        .all()
    )

    memories, _ = await store.list_memories(
        filters={"status": "active"}, limit=settings.merge_suggest_scan_limit
    )

    queued = 0
    for mem in memories:
        if mem.embedding is None:
            continue
        neighbors = await store.find_similar(list(mem.embedding), threshold=low, limit=5)
        for other, score in neighbors:
            if str(other.id) == str(mem.id):
                continue

            entities_a = set((mem.properties or {}).get("entities") or [])
            entities_b = set((other.properties or {}).get("entities") or [])
            overlap = bool(entities_a & entities_b)

            # Review band (mirrors merge_suggestions), OR shared entities —
            # the latter still applies even if score >= high, since a pair
            # that slipped past auto-merge and coexists is exactly the kind
            # of fragment this one-time cleanup exists to surface.
            if not (score < high or overlap):
                continue

            ref = _pair_ref(mem.id, other.id)
            if ref in seen:
                continue
            seen.add(ref)

            session.add(
                Approval(
                    tenant_id=tenant_id,
                    kind="merge",
                    source="cleanup",
                    source_ref=ref,
                    title="Merge fragment/duplicate memories",
                    detail=(
                        f"cleanup · {round(score * 100)}% similar"
                        f"{' · shared entities' if overlap else ''} · "
                        f"“{(mem.content or '')[:60]}” ~ "
                        f"“{(other.content or '')[:60]}”"
                    ),
                    payload={
                        "memory_id_a": str(mem.id),
                        "memory_id_b": str(other.id),
                        "similarity": round(float(score), 4),
                    },
                )
            )
            queued += 1

    if queued:
        await session.flush()
    return queued


async def cleanup_memories_tenant(ctx: dict, tenant_id: str) -> dict:
    """Queue merge approvals for fragment/duplicate memories (one tenant).

    One-time cleanup job — triggered via ``POST /admin/jobs/cleanup-memories``.
    Idempotent (see ``_pair_ref``); does not auto-merge or auto-delete.
    """
    set_tenant_context(tenant_id, "system")
    store = PostgresMemoryStore()
    async with async_session() as session:
        queued = await _cleanup_tenant(session, store, tenant_id)
        await session.commit()
    logger.info("Cleanup for tenant %s: queued %d merge approvals", tenant_id, queued)
    return {"tenant_id": tenant_id, "queued": queued}


async def cleanup_memories_all(ctx: dict) -> dict:
    """Run the one-time cleanup across all tenants with memories."""
    async with async_session() as session:
        result = await session.execute(select(Memory.tenant_id).distinct())
        tenant_ids = [row[0] for row in result.fetchall()]

    total = 0
    for tid in tenant_ids:
        try:
            res = await cleanup_memories_tenant(ctx, tid)
            total += res.get("queued", 0)
        except Exception:
            logger.exception("Cleanup failed for tenant %s", tid)
    return {"tenants": len(tenant_ids), "queued": total}

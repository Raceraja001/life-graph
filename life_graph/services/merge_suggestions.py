"""Merge-suggestion producer — additive, nightly.

Scans active memories for pairs whose cosine similarity lands in the review
band ``[merge_review_low, dedup_threshold)`` — near-duplicates that the ingest
auto-merge (≥ dedup_threshold) leaves alone — and queues a ``kind='merge'``
approval for each. Changes nothing existing: it only surfaces pairs that
currently coexist. Approving merges them (see ApprovalService._apply_merge);
rejecting leaves both, and the resolved row keeps the pair from re-surfacing.

See docs/specs/approvals-feed.md.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from life_graph.config import settings
from life_graph.models.db import Approval
from life_graph.storage.postgres import PostgresMemoryStore


def _pair_key(id_a: str, id_b: str) -> str:
    """Stable, order-independent key for a memory pair (fits source_ref/128)."""
    return "|".join(sorted((id_a, id_b)))


class MergeSuggestionService:
    """Queues merge approvals for near-duplicate memory pairs."""

    def __init__(self, session: AsyncSession, store: PostgresMemoryStore) -> None:
        self.session = session
        self.store = store

    async def scan_and_queue(self, tenant_id: str) -> int:
        """Scan active memories and queue merge approvals. Returns count queued.

        Idempotent: pairs that already have a merge approval (pending OR resolved)
        are skipped, so nothing re-surfaces after you've acted on it.
        """
        low = settings.merge_review_low
        high = settings.dedup_threshold
        if low >= high:
            return 0

        # Pairs already queued/resolved — skip them.
        seen: set[str] = set(
            (
                await self.session.execute(
                    select(Approval.source_ref).where(
                        Approval.tenant_id == tenant_id,
                        Approval.source == "curator",
                        Approval.source_ref.is_not(None),
                    )
                )
            )
            .scalars()
            .all()
        )

        memories, _ = await self.store.list_memories(
            filters={"status": "active"}, limit=settings.merge_suggest_scan_limit
        )

        queued = 0
        for mem in memories:
            if mem.embedding is None:
                continue
            neighbors = await self.store.find_similar(list(mem.embedding), threshold=low, limit=5)
            for other, score in neighbors:
                if str(other.id) == str(mem.id) or score >= high:
                    continue  # itself, or already handled by auto-merge
                ref = _pair_key(str(mem.id), str(other.id))
                if ref in seen:
                    continue
                seen.add(ref)
                self.session.add(
                    Approval(
                        tenant_id=tenant_id,
                        kind="merge",
                        source="curator",
                        source_ref=ref,
                        title="Merge 2 near-duplicate memories",
                        detail=(
                            f"curator · {round(score * 100)}% similar · "
                            f"“{(mem.content or '')[:60]}” ~ “{(other.content or '')[:60]}”"
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
            await self.session.flush()
        return queued

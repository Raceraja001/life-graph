"""hybrid_search orders tied scores the same way every time (#458).

Equal keyword scores (and equal vector distances) used to come back in whatever
row order the plan produced, so the same question could rank its candidates
differently from one run to the next. That moved records across the snapshot's
link-expansion boundary and made the CI context-quality gate flaky. Ties are
now broken by md5(content), then id. Embeddings cannot be written under pytest
(tests/conftest.py fakes the Vector type), so this exercises the keyword leg and
the final fused order.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest

from life_graph.core.tenant import set_tenant_context
from tests.integration.conftest import skip_on_db_error

WORD = f"quillon{uuid.uuid4().hex[:6]}"
# Same length and shape, one shared rare word each: identical keyword scores.
CONTENTS = [f"{WORD} note {c}{c}{c}" for c in "abcdefgh"]


async def _seed(tenant: str, contents: list[str]) -> None:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        for content in contents:
            s.add(
                Memory(
                    content=content,
                    tenant_id=tenant,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    importance=0.5,
                    tags=["test"],
                    status="active",
                    trust_tier="verified",
                    source_type="test",
                )
            )
            # One commit per row so the heap order follows the list order.
            await s.commit()


async def _order(tenant: str) -> list[tuple[str, float]]:
    from life_graph.storage.postgres import PostgresMemoryStore

    set_tenant_context(tenant)
    hits = await PostgresMemoryStore().hybrid_search(
        embedding=[0.0] * 1024, query_text=WORD, limit=len(CONTENTS)
    )
    return [(m.content, round(score, 9)) for m, score in hits]


async def _cleanup(tenants: list[str]) -> None:
    from sqlalchemy import delete

    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        await s.execute(delete(Memory).where(Memory.tenant_id.in_(tenants)))
        await s.commit()


@pytest.mark.asyncio
@skip_on_db_error
async def test_tied_scores_come_back_in_one_stable_order():
    forward, backward = f"tie_f_{uuid.uuid4().hex[:8]}", f"tie_b_{uuid.uuid4().hex[:8]}"
    try:
        await _seed(forward, CONTENTS)
        await _seed(backward, list(reversed(CONTENTS)))

        a, b = await _order(forward), await _order(backward)

        assert len(a) == len(CONTENTS)
        # The keyword leg turns the tie into ranks 1..n, so scores differ; the
        # order of those ranks is what used to depend on the heap order.
        # Insertion order no longer matters...
        assert [c for c, _ in a] == [c for c, _ in b]
        # ...and the tie-break is the documented one.
        assert [c for c, _ in a] == sorted(
            CONTENTS, key=lambda c: hashlib.md5(c.encode()).hexdigest()
        )
        # Asking again gives the same answer.
        assert await _order(forward) == a
    finally:
        await _cleanup([forward, backward])

"""The keyword leg of hybrid_search ranks rare question words above common ones.

ts_rank_cd does not know how common a word is. With "any word" matching
(_or_tsquery), a note sharing two everyday words with the question outranked
the only note holding the rare word that names what was asked. Since
2026-11-25 each question word scores BM25's IDF over the tenant's searchable
memories. No embeddings are written here, so only the keyword leg ranks.
"""

from __future__ import annotations

import hashlib
import uuid

import pytest

from life_graph.core.tenant import set_tenant_context
from tests.integration.conftest import skip_on_db_error


async def _seed(tenant: str, contents: list[str], status: str = "active") -> None:
    from life_graph.models.db import Memory
    from life_graph.storage.database import async_session

    async with async_session() as s:
        for content in contents:
            s.add(
                Memory(
                    content=content,
                    tenant_id=tenant,
                    content_hash=hashlib.sha256(content.encode()).hexdigest(),
                    status=status,
                    trust_tier="self",
                    source_type="test",
                )
            )
        await s.commit()


async def _cleanup(tenant: str) -> None:
    from sqlalchemy import text

    from life_graph.storage.database import async_session

    async with async_session() as s:
        await s.execute(text("DELETE FROM memories WHERE tenant_id = :t"), {"t": tenant})
        await s.commit()


async def _search(tenant: str, question: str) -> list[str]:
    from life_graph.storage.postgres import PostgresMemoryStore

    set_tenant_context(tenant)
    hits = await PostgresMemoryStore().hybrid_search(
        embedding=[0.0] * 1024, query_text=question, limit=20
    )
    return [m.content for m, _ in hits]


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_rare_question_word_outranks_two_common_ones():
    tenant = f"idf_{uuid.uuid4().hex[:10]}"
    rare = "Cricket practice moved to Saturday."
    try:
        await _seed(tenant, [f"Another long work day, entry {i}." for i in range(8)] + [rare])
        found = await _search(tenant, "Which day do I play cricket after work?")
        # Under ts_rank_cd the eight "work day" notes (two matched words each)
        # all came before the one note that answers (one matched word).
        assert found[0] == rare
        assert len(found) == 9
    finally:
        await _cleanup(tenant)


@pytest.mark.asyncio
@skip_on_db_error
async def test_word_rarity_is_counted_over_searchable_memories_only():
    """Twelve pending notes say "cricket"; among active memories it is rarer
    than "club". Counted over every status, "cricket" would look common and a
    club note would come first; counted over what search may return, the one
    cricket note does."""
    tenant = f"idf_{uuid.uuid4().hex[:10]}"
    answer = "Cricket on Saturday mornings."
    try:
        await _seed(tenant, [f"Cricket note {i} waiting for review." for i in range(12)], "pending")
        await _seed(tenant, [answer] + [f"Chess club on Sunday, week {i}." for i in range(3)])
        found = await _search(tenant, "When is the cricket club?")
        assert found[0] == answer
        assert all("review" not in c for c in found)
    finally:
        await _cleanup(tenant)


@pytest.mark.asyncio
@skip_on_db_error
async def test_a_question_of_stop_words_only_finds_nothing_by_keyword():
    tenant = f"idf_{uuid.uuid4().hex[:10]}"
    try:
        await _seed(tenant, ["Another long work day."])
        assert await _search(tenant, "what is it?") == []
    finally:
        await _cleanup(tenant)

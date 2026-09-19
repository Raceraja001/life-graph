"""Memories stored verbatim must be embedded and deduplicated like ingested ones.

POST /memories has two paths that skip MemoryManager.ingest(): structured input
(tags + importance + short content) and the fallback when extraction yields
nothing. Only the fallback computed an embedding and ran the exact-hash dedup
check. Structured memories were stored with no embedding — invisible to vector
search for good — and re-submitting one inserted a duplicate row every time.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.api.memories import create_memory
from life_graph.models.schemas import MemoryCreate

_VECTOR = [0.1] * 8


def _row(content: str) -> SimpleNamespace:
    """Enough of a Memory row for MemoryResponse.model_validate."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        content=content,
        reasoning=None,
        tags=["preference"],
        properties={},
        importance=0.4,
        confidence=0.5,
        source_type="manual",
        created_at=datetime.now(UTC),
        status="pending",
        access_count=0,
        extraction_tier="manual",
        extraction_confidence=None,
    )


def _fakes(*, duplicate=None, ingested=None):
    manager = SimpleNamespace(
        generate_embedding=AsyncMock(return_value=_VECTOR),
        ingest=AsyncMock(return_value=ingested or []),
    )
    store = SimpleNamespace(
        find_exact_duplicate=AsyncMock(return_value=duplicate),
        store=AsyncMock(side_effect=lambda body, **kw: _row(body.content)),
    )
    return manager, store


def _structured(content: str = "Prefers tea") -> MemoryCreate:
    return MemoryCreate(content=content, tags=["preference"], importance=0.4, source_type="manual")


@pytest.mark.asyncio
async def test_structured_input_is_embedded():
    manager, store = _fakes()

    await create_memory(_structured(), manager=manager, store=store)

    manager.ingest.assert_not_awaited()  # structured input skips extraction
    manager.generate_embedding.assert_awaited_once_with("Prefers tea")
    kwargs = store.store.await_args.kwargs
    assert kwargs["embedding"] == _VECTOR
    assert kwargs["extraction_tier"] == "manual"


@pytest.mark.asyncio
async def test_structured_duplicate_returns_existing_row():
    existing = _row("Prefers tea")
    manager, store = _fakes(duplicate=existing)

    await create_memory(_structured(), manager=manager, store=store)

    store.store.assert_not_awaited()
    manager.generate_embedding.assert_not_awaited()  # no wasted embedding call


@pytest.mark.asyncio
async def test_extraction_fallback_still_embeds():
    """The path that already worked must keep working after the refactor."""
    manager, store = _fakes(ingested=[])
    body = MemoryCreate(
        content="an unparseable scrap of text with no clear facts", source_type="manual"
    )

    await create_memory(body, manager=manager, store=store)

    manager.ingest.assert_awaited_once()
    assert store.store.await_args.kwargs["embedding"] == _VECTOR

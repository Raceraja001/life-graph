"""Multimodal capture must carry its surface's trust tier into storage.

``PostgresMemoryStore.store`` defaults an absent ``trust_tier`` to ``verified``.
``ingest_or_fallback`` used to omit it entirely, so every voice / image /
document capture was persisted as trusted regardless of provenance. The
dangerous case is ``document``: it is not in the default-deny surface map, so
it must resolve to ``EXTERNAL`` — an uploaded file is arbitrary third-party
content, and tagging it ``verified`` defeats the ``is_untrusted`` fencing and
the ``is_excluded_from_agents`` check that keep untrusted text out of prompts.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.core.trust import TrustTier
from life_graph.services.multimodal import ingest_or_fallback


def _manager(*, ingest_returns: list) -> SimpleNamespace:
    """A MemoryManager stand-in recording what it was asked to persist."""
    return SimpleNamespace(
        ingest=AsyncMock(return_value=ingest_returns),
        generate_embedding=AsyncMock(return_value=[0.0]),
        store=SimpleNamespace(store=AsyncMock(return_value=object())),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("document", TrustTier.EXTERNAL),
        ("voice", TrustTier.SELF),
        ("image", TrustTier.SELF),
        ("something_unmapped", TrustTier.EXTERNAL),
    ],
)
async def test_ingest_carries_the_surface_trust_tier(source: str, expected: TrustTier) -> None:
    manager = _manager(ingest_returns=[object()])

    await ingest_or_fallback(manager, "some captured text", source)

    assert manager.ingest.await_args.kwargs["trust_tier"] == expected.value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("document", TrustTier.EXTERNAL),
        ("voice", TrustTier.SELF),
        ("something_unmapped", TrustTier.EXTERNAL),
    ],
)
async def test_raw_text_fallback_carries_the_same_tier(source: str, expected: TrustTier) -> None:
    """The no-facts fallback path stores directly and must not skip the tier."""
    manager = _manager(ingest_returns=[])

    await ingest_or_fallback(manager, "some captured text", source)

    manager.store.store.assert_awaited_once()
    assert manager.store.store.await_args.kwargs["trust_tier"] == expected.value


@pytest.mark.asyncio
async def test_an_uploaded_document_is_never_stored_as_verified() -> None:
    """The specific regression: 'verified' is what the store defaults to."""
    manager = _manager(ingest_returns=[])

    await ingest_or_fallback(manager, "contents of an uploaded PDF", "document")

    for call in (manager.ingest.await_args, manager.store.store.await_args):
        assert call.kwargs["trust_tier"] != TrustTier.VERIFIED.value

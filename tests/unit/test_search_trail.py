"""Search can fall back to the raw capture trail.

Extraction is lossy. Across several 2026 studies, retrieving verbatim text
beat retrieving LLM-extracted facts by 16–22 points, and fine-grained
extraction collapsed multi-hop accuracy outright. We already keep every
original in `capture_events`, so the sentence a fact came from is usually
still there when the fact is wrong, mangled, or was never extracted at all.

Measured on this instance's own gold set: hit rate 0.80 → 0.85, MRR 0.606 →
0.656, with one case answered only by the trail — the NTFS-versus-ext4
decision, whose memory had been deleted as malformed while the prompt that
produced it survived.

Opt-in (`include_trail`), so no existing caller's response shape changes.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from life_graph.api.search import _TRAIL_EXCERPT_CHARS, _search_trail


def _event(content: str, surface: str = "cli") -> SimpleNamespace:
    return SimpleNamespace(
        id="3f1b0f1e-0000-0000-0000-00000000000a",
        surface=surface,
        content=content,
        created_at=datetime.now(UTC),
    )


def _body(limit: int = 10):
    return SimpleNamespace(query="where should the files live", limit=limit)


@pytest.mark.asyncio
async def test_passages_carry_the_verbatim_text():
    store = SimpleNamespace(
        search_capture_events=AsyncMock(
            return_value=[(_event("having those files in NTFS or move to ext4?"), 0.42)]
        )
    )

    passages = await _search_trail(store, _body())

    assert len(passages) == 1
    assert passages[0].excerpt == "having those files in NTFS or move to ext4?"
    assert passages[0].surface == "cli"
    assert passages[0].rank == pytest.approx(0.42)


@pytest.mark.asyncio
async def test_mechanical_surfaces_are_excluded():
    """A question about a decision must not return the shell command that
    happened to be running at the time. The surfaces the spine declines to
    extract are the same ones not worth searching for an answer."""
    store = SimpleNamespace(search_capture_events=AsyncMock(return_value=[]))

    await _search_trail(store, _body())

    excluded = store.search_capture_events.await_args.kwargs["exclude_surfaces"]
    assert "tool_exhaust" in excluded


@pytest.mark.asyncio
async def test_a_long_capture_is_trimmed():
    """A capture can be a 60kB report; the point is to show the words that
    matched, not to re-deliver the document."""
    store = SimpleNamespace(
        search_capture_events=AsyncMock(return_value=[(_event("x" * 5000), 0.1)])
    )

    passages = await _search_trail(store, _body())

    assert len(passages[0].excerpt) == _TRAIL_EXCERPT_CHARS + 1  # the ellipsis
    assert passages[0].excerpt.endswith("…")


@pytest.mark.asyncio
async def test_the_trail_is_capped_independently_of_the_memory_limit():
    """Passages are long next to a fact, so a caller asking for 50 memories
    should not also get 50 documents."""
    store = SimpleNamespace(search_capture_events=AsyncMock(return_value=[]))

    await _search_trail(store, _body(limit=50))

    assert store.search_capture_events.await_args.kwargs["limit"] == 5

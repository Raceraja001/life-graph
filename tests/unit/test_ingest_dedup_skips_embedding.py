# tests/unit/test_ingest_dedup_skips_embedding.py
"""Unit tests for MemoryManager.ingest()'s exact-hash pre-check: facts that
are exact duplicates of an existing memory should never pay for an embedding
call, and non-duplicate facts should still get embedded and processed."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.core.memory_manager import MemoryManager
from life_graph.extraction.pipeline import ExtractionResult
from life_graph.extraction.rules import ExtractedFact


def _make_manager(monkeypatch, *, existing_for: dict[str, object]):
    """Build a MemoryManager with extractor/store/embedding mocked out.

    existing_for maps fact content -> the "existing memory" that
    find_exact_duplicate should return for that content's hash (or no entry
    for "no duplicate").
    """
    mgr = MemoryManager.__new__(MemoryManager)  # bypass __init__/DI

    embed_calls: list[str] = []

    async def fake_embed(text: str):
        embed_calls.append(text)
        return [0.1, 0.2, 0.3]

    async def fake_find_exact_duplicate(content_hash: str):
        return existing_for.get(content_hash)

    touched: list[str] = []

    async def fake_touch(memory_id):
        touched.append(memory_id)

    processed: list[str] = []

    async def fake_process_fact(fact, context, source, skip_dedup, trust_tier, embedding=None):
        processed.append(fact.content)
        return SimpleNamespace(id=f"new-{fact.content}")

    monkeypatch.setattr(mgr, "_generate_embedding", fake_embed)
    monkeypatch.setattr(mgr, "_process_fact", fake_process_fact)
    mgr._store = SimpleNamespace(
        find_exact_duplicate=fake_find_exact_duplicate,
        touch=fake_touch,
    )
    return mgr, embed_calls, touched, processed


def _extraction_result(facts: list[ExtractedFact]) -> ExtractionResult:
    return ExtractionResult(facts=facts)


@pytest.mark.asyncio
async def test_exact_duplicate_fact_skips_embedding_and_process_fact(monkeypatch):
    import hashlib

    dup_content = "I like pizza"
    dup_hash = hashlib.sha256(dup_content.strip().lower().encode()).hexdigest()
    existing = SimpleNamespace(id="existing-1")

    mgr, embed_calls, touched, processed = _make_manager(
        monkeypatch, existing_for={dup_hash: existing}
    )
    facts = [ExtractedFact(content=dup_content, fact_type="preference", confidence=0.9)]

    async def _extract(text, capture=False):
        return _extraction_result(facts)

    mgr._extractor = SimpleNamespace(extract=_extract)

    result = await mgr.ingest(dup_content)

    assert result == [existing]
    assert embed_calls == []  # never embedded — exact dup short-circuited first
    assert processed == []  # never reached _process_fact
    assert touched == ["existing-1"]


@pytest.mark.asyncio
async def test_mixed_batch_only_embeds_non_duplicate_facts(monkeypatch):
    import hashlib

    dup_content = "I like pizza"
    new_content = "I hate mushrooms"
    dup_hash = hashlib.sha256(dup_content.strip().lower().encode()).hexdigest()
    existing = SimpleNamespace(id="existing-1")

    mgr, embed_calls, touched, processed = _make_manager(
        monkeypatch, existing_for={dup_hash: existing}
    )
    facts = [
        ExtractedFact(content=dup_content, fact_type="preference", confidence=0.9),
        ExtractedFact(content=new_content, fact_type="anti_preference", confidence=0.9),
    ]

    async def _extract(text, capture=False):
        return _extraction_result(facts)

    mgr._extractor = SimpleNamespace(extract=_extract)

    result = await mgr.ingest(f"{dup_content}. {new_content}.")

    assert embed_calls == [new_content]  # only the non-duplicate was embedded
    assert processed == [new_content]  # only the non-duplicate reached _process_fact
    assert touched == ["existing-1"]
    assert len(result) == 2

# tests/unit/test_store_facts.py
"""Unit test for MemoryManager.store_facts (store-side path, _process_fact mocked)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from life_graph.core.memory_manager import MemoryManager
from life_graph.extraction.rules import ExtractedFact


@pytest.mark.asyncio
async def test_store_facts_processes_each_fact(monkeypatch):
    mgr = MemoryManager.__new__(MemoryManager)  # bypass __init__/DI
    m1, m2 = SimpleNamespace(id=1), SimpleNamespace(id=2)
    calls = []

    async def fake_process(fact, context, source, skip_dedup=False, trust_tier=None):
        calls.append((fact.content, source))
        return {"a": m1, "b": m2, "c": None}[fact.content]

    monkeypatch.setattr(mgr, "_process_fact", fake_process)
    facts = [
        ExtractedFact(content="a", fact_type="fact", confidence=0.7),
        ExtractedFact(content="b", fact_type="decision", confidence=0.7),
        ExtractedFact(content="c", fact_type="fact", confidence=0.7),  # duplicate -> None
    ]
    stored = await mgr.store_facts(facts, context={"tool": "claude-code"}, source="transcript")
    assert stored == [m1, m2]  # None (dup) filtered out
    assert calls == [("a", "transcript"), ("b", "transcript"), ("c", "transcript")]

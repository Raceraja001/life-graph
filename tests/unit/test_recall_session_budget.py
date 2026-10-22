"""Proactive recall keeps working past the second session in a process.

The engine is one process-wide instance; its "per-session" surfacing counter
was never reset, so after about two session starts recall returned nothing
until the server restarted (found 2026-10-22). And cooled-down memories were
filtered after cutting to the maximum, so repeat recalls came back shorter.
"""

from __future__ import annotations

from life_graph.config import settings
from life_graph.services import recall as recall_mod
from tests.unit.test_recall_engine import _engine, _Memory


async def _start(engine):
    payload = await engine.session_start_recall({"project": "x"})
    return payload.identity + payload.decisions + payload.warnings + payload.intentions


async def test_each_session_start_gets_a_fresh_budget(monkeypatch):
    monkeypatch.setattr(recall_mod, "_COOLDOWN_SECONDS", 0)  # no cooldown: only the budget
    rows = [_Memory(content=f"m{i}", tags=["decision"]) for i in range(8)]
    engine = _engine(rows)
    counts = [len(await _start(engine)) for _ in range(4)]
    assert all(n > 0 for n in counts), counts


async def test_cooled_down_memories_are_backfilled(monkeypatch):
    rows = [_Memory(content=f"m{i}", tags=["decision"]) for i in range(12)]
    engine = _engine(rows)
    first = await engine.session_start_recall({"project": "x"})
    second = await engine.session_start_recall({"project": "x"})
    n = settings.recall_max_session_start
    shown_first = {str(m.id) for m in first.decisions}
    shown_second = {str(m.id) for m in second.decisions}
    assert len(shown_first) == n and len(shown_second) == n
    assert not shown_first & shown_second  # the cooldown still holds

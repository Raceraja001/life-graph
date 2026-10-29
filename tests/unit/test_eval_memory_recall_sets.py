"""The recall eval's sets grow without changing: ``build`` asks only about
memories it has no question for, so earlier numbers stay comparable."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval_memory_recall.py"


@pytest.fixture
def ev(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("eval_memory_recall", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "OUT_DIR", tmp_path)

    class Client:
        async def chat_local_only(self, messages, **_kw):
            return json.dumps({"questions": ["Do I have a dog?", "Where do I bank?"]})

    import life_graph.api.dependencies as deps

    monkeypatch.setattr(deps, "get_lm_client", lambda: Client())
    asked: list[list[str]] = []

    async def numbered(_client, _model, _prompt, items):
        asked.append(items)
        return {i: f"Q about: {c}" for i, c in enumerate(items)}

    monkeypatch.setattr(mod, "_numbered", numbered)
    return SimpleNamespace(mod=mod, asked=asked, dir=tmp_path)


async def test_a_rebuild_adds_questions_only_for_new_memories(ev, monkeypatch):
    memories = [("m1", "The owner uses a Realme X2 Pro."), ("m2", "The owner prefers local HTML.")]

    async def active(_tenant):
        return list(memories)

    monkeypatch.setattr(ev.mod, "_active", active)
    await ev.mod.build("t", "live", unanswerable=2)
    first = json.loads((ev.dir / "t_live.json").read_text())["cases"]
    assert [c["memory_id"] for c in first] == ["m1", "m2", None, None]

    memories.append(("m3", "The owner retired port 3001."))
    await ev.mod.build("t", "live", unanswerable=2)
    second = json.loads((ev.dir / "t_live.json").read_text())["cases"]

    assert second[:4] == first  # untouched, in order
    assert [c["memory_id"] for c in second[4:]] == ["m3"]  # no second unanswerable batch
    assert ev.asked == [[m[1] for m in memories[:2]], [memories[2][1]]]


async def test_a_tamil_copy_keeps_the_answer_and_the_english(ev):
    cases = [
        {"q": "Which phone do I use?", "memory_id": "m1", "memory": "Realme"},
        {"q": "Do I have a dog?", "memory_id": None},
    ]
    (ev.dir / "t_recall.json").write_text(json.dumps({"tenant": "t", "cases": cases}))
    await ev.mod.translate("t", "recall", n=30)
    ta = json.loads((ev.dir / "t_recall_ta.json").read_text())
    assert ta["from"] == "recall"
    assert ta["cases"] == [
        {
            "q": "Q about: Which phone do I use?",
            "memory_id": "m1",
            "memory": "Realme",
            "en": "Which phone do I use?",
        }
    ]


async def test_recall_refuses_a_pool_it_cannot_read(ev):
    with pytest.raises(ValueError, match="active memories only"):
        await ev.mod._search("recall", "anything", 10, "archived")

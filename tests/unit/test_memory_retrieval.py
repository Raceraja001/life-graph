"""The relevance judge keeps only memories that help answer — or none (services/memory_retrieval.py)."""

from __future__ import annotations

import json
import uuid
from types import SimpleNamespace

import pytest

from life_graph.services.memory_retrieval import judge, retrieve


class _Client:
    def __init__(self, reply):
        self.reply, self.calls = reply, []

    # Only the local-only method exists: a cloud call would fail the test.
    async def chat_local_only(self, messages, **kw):
        self.calls.append((messages, kw))
        return self.reply


def _wire(monkeypatch, reply, hits=(), embedding=(0.1,)):
    import life_graph.api.dependencies as deps

    client = _Client(reply)

    class _Manager:
        async def generate_embedding(self, text):
            return list(embedding) if embedding else None

    class _Store:
        async def hybrid_search(self, **kw):
            assert kw["statuses"] == ("active",)
            return list(hits)

    monkeypatch.setattr(deps, "get_lm_client", lambda: client)
    monkeypatch.setattr(deps, "get_memory_manager", lambda: _Manager())
    monkeypatch.setattr(deps, "get_store", lambda: _Store())
    return client


def _mem(text):
    return SimpleNamespace(id=uuid.uuid4(), content=text, created_at=None)


@pytest.mark.parametrize(
    ("reply", "expected"),
    [
        ('{"relevant": [2, 1]}', [1, 0]),
        ('{"relevant": []}', []),
        ('{"relevant": [9, 2, 2, "x"]}', [1]),  # out of range, repeats, junk dropped
        ("not json", None),
        ("{}", None),
    ],
)
async def test_judge_reads_the_models_answer(monkeypatch, reply, expected):
    _wire(monkeypatch, reply)
    assert await judge("q?", ["a", "b"]) == expected


async def test_retrieve_keeps_what_the_judge_picked_in_its_order(monkeypatch):
    a, b, c = _mem("insurance renews in March"), _mem("frontend port"), _mem("short answers")
    client = _wire(
        monkeypatch, json.dumps({"relevant": [3, 1]}), hits=[(a, 0.9), (b, 0.8), (c, 0.7)]
    )
    assert await retrieve("When does my insurance renew?") == [c, a]
    user = client.calls[0][0][1]["content"]
    assert "Question: When does my insurance renew?" in user and "2. frontend port" in user


async def test_retrieve_can_find_nothing(monkeypatch):
    _wire(monkeypatch, '{"relevant": []}', hits=[(_mem("frontend port"), 0.5)])
    assert await retrieve("What is my blood group?") == []


async def test_a_judge_outage_falls_back_to_the_search_order(monkeypatch):
    a, b = _mem("x"), _mem("y")
    _wire(monkeypatch, "", hits=[(a, 0.9), (b, 0.8)])
    assert await retrieve("q", limit=1) == [a]


async def test_no_embedding_is_not_nothing_found(monkeypatch):
    _wire(monkeypatch, "{}", embedding=None)
    assert await retrieve("q") is None

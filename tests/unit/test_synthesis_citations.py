"""Citation parsing: [Memory N] tags map to the Nth memory's id."""

import pytest

from life_graph.services.synthesis import SynthesisService, parse_citations


def test_parse_citations_maps_to_ids():
    ids = ["aaa", "bbb", "ccc"]
    citations = parse_citations("Your insurance is due Aug 15 [Memory 1]. Also [Memory 3].", ids)
    assert citations == ["aaa", "ccc"]


def test_parse_citations_dedupes_and_drops_out_of_range():
    ids = ["aaa", "bbb"]
    citations = parse_citations("[Memory 1] [Memory 1] [Memory 5] [Memory 2]", ids)
    assert citations == ["aaa", "bbb"]  # dup dropped, out-of-range 5 dropped


class _FakeClient:
    def __init__(self, reply: str):
        self._reply = reply

    async def chat(self, **kwargs):
        return self._reply


@pytest.mark.asyncio
async def test_synthesize_returns_citations():
    svc = SynthesisService(client=_FakeClient("It is due Friday [Memory 2]."))
    memories = [
        {"id": "id-a", "content": "car service Monday"},
        {"id": "id-b", "content": "insurance due Friday"},
    ]
    result = await svc.synthesize("when is insurance due?", memories)
    assert result["citations"] == ["id-b"]
    assert result["answer"] == "It is due Friday [Memory 2]."
    assert result["source_count"] == 2

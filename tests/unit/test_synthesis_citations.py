"""Citation parsing: [Memory N] tags map to the Nth memory's id.

Also covers renumber_citations, which is what keeps the contract 1:1: the
answer text returned to callers always has [Memory J] aligned with
citations[J-1] — no gaps from dedup, no dangling indices from out-of-range
tags. See the "Critical: citation chips can point at the wrong memory" fix.
"""

import pytest

from life_graph.services.synthesis import SynthesisService, parse_citations, renumber_citations


def test_parse_citations_maps_to_ids():
    ids = ["aaa", "bbb", "ccc"]
    citations = parse_citations("Your insurance is due Aug 15 [Memory 1]. Also [Memory 3].", ids)
    assert citations == ["aaa", "ccc"]


def test_parse_citations_dedupes_and_drops_out_of_range():
    ids = ["aaa", "bbb"]
    citations = parse_citations("[Memory 1] [Memory 1] [Memory 5] [Memory 2]", ids)
    assert citations == ["aaa", "bbb"]  # dup dropped, out-of-range 5 dropped


def test_renumber_citations_closes_gaps_from_dedup():
    # 3-memory context, but only memories 1 and 3 are actually cited (and
    # memory 1 is cited twice) — without renumbering, citations = ["a", "c"]
    # (2 elements) while the answer still says "[Memory 3]", which has no
    # matching index in a 2-element list.
    ids = ["a", "b", "c"]
    answer = "A [Memory 1] B [Memory 3] C [Memory 1]"
    renumbered, citations = renumber_citations(answer, ids)
    assert citations == ["a", "c"]
    assert renumbered == "A [Memory 1] B [Memory 2] C [Memory 1]"
    # the invariant this whole fix exists for: [Memory J] <-> citations[J-1]
    assert citations[0] == "a"  # [Memory 1]
    assert citations[1] == "c"  # [Memory 2]


def test_renumber_citations_strips_out_of_range_tokens():
    ids = ["a", "b"]
    answer = "X [Memory 1] Y [Memory 5] Z"
    renumbered, citations = renumber_citations(answer, ids)
    assert citations == ["a"]
    assert "[Memory 5]" not in renumbered
    assert renumbered == "X [Memory 1] Y Z"


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
    # Renumbered: only memory 2 (of 2) was actually cited, so it becomes the
    # sole, sequential "[Memory 1]" — aligned with citations[0] == "id-b".
    assert result["answer"] == "It is due Friday [Memory 1]."
    assert result["source_count"] == 2


@pytest.mark.asyncio
async def test_synthesize_renumbers_answer_to_match_citations():
    svc = SynthesisService(
        client=_FakeClient("Car Monday [Memory 1]; insurance Friday [Memory 3].")
    )
    memories = [
        {"id": "id-a", "content": "car service Monday"},
        {"id": "id-b", "content": "unrelated memory"},
        {"id": "id-c", "content": "insurance due Friday"},
    ]
    result = await svc.synthesize("what's due this week?", memories)
    assert result["citations"] == ["id-a", "id-c"]
    assert result["answer"] == "Car Monday [Memory 1]; insurance Friday [Memory 2]."

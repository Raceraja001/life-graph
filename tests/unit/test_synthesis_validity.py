"""The synthesis prompt says when a memory is replaced or has an end date.

An ``as_of`` question to /ask can bring back a superseded or since-ended fact;
the model has to be told, or it states an old value as current. A current,
open-ended memory reads exactly as before.
"""

import pytest

from life_graph.services.synthesis import SynthesisService


class _Capture:
    def __init__(self):
        self.messages = []

    async def chat_local_only(self, **kwargs):  # synthesis is local-only (D25)
        self.messages = kwargs["messages"]
        return "Chennai [Memory 1]."


def _mem(mid, **extra):
    return {
        "id": mid,
        "content": f"fact {mid}",
        "tags": ["t"],
        "importance": 0.5,
        "created_at": "2026-11-01",
        **extra,
    }


@pytest.mark.asyncio
async def test_replaced_and_ending_memories_are_labelled_current_ones_unchanged():
    client = _Capture()
    await SynthesisService(client=client).synthesize(
        "where?",
        [
            _mem("a", status="superseded", valid_until="2026-11-20 00:00:00+00:00"),
            _mem("b", status="active", valid_until=None),
            _mem("c"),
        ],
    )
    prompt = client.messages[-1]["content"]
    assert (
        "[Memory 1] (tags: t, importance: 0.5, date: 2026-11-01, status: superseded,"
        " true until: 2026-11-20 00:00:00+00:00)\nfact a"
    ) in prompt
    assert "[Memory 2] (tags: t, importance: 0.5, date: 2026-11-01)\nfact b" in prompt
    assert "[Memory 3] (tags: t, importance: 0.5, date: 2026-11-01)\nfact c" in prompt

"""Unit tests for the second-opinion reviewer."""

from __future__ import annotations

from life_graph.services.second_opinion import SecondOpinionReviewer


class StubLLM:
    def __init__(self, reply="", raise_exc=False):
        self.reply = reply
        self.raise_exc = raise_exc
        self.calls = 0

    async def chat(self, messages, **kw):
        self.calls += 1
        if self.raise_exc:
            raise RuntimeError("llm down")
        return self.reply


async def test_disabled_is_noop_and_approves():
    llm = StubLLM('{"approved": false, "concern": "bug"}')
    r = SecondOpinionReviewer(llm=llm, enabled=False)
    v = await r.review("code_fix", "do x", "some output")
    assert v.approved is True
    assert v.ran is False
    assert llm.calls == 0  # never called the model


async def test_no_llm_approves():
    r = SecondOpinionReviewer(llm=None, enabled=True)
    v = await r.review("code_fix", "do x", "output")
    assert v.approved is True and v.ran is False


async def test_empty_output_approves_without_call():
    llm = StubLLM('{"approved": false}')
    r = SecondOpinionReviewer(llm=llm, enabled=True)
    v = await r.review("code_fix", "do x", "")
    assert v.approved is True and v.ran is False
    assert llm.calls == 0


async def test_dissent_blocks():
    llm = StubLLM('{"approved": false, "concern": "SQL injection in query builder"}')
    r = SecondOpinionReviewer(llm=llm, enabled=True)
    v = await r.review("code_fix", "add search", "def q(s): return f\"...{s}\"")
    assert v.ran is True
    assert v.approved is False
    assert "injection" in v.concern


async def test_approval_passes():
    llm = StubLLM('{"approved": true, "concern": ""}')
    r = SecondOpinionReviewer(llm=llm, enabled=True)
    v = await r.review("code_fix", "x", "clean output")
    assert v.approved is True and v.ran is True
    assert v.concern is None


async def test_llm_error_fails_open():
    llm = StubLLM(raise_exc=True)
    r = SecondOpinionReviewer(llm=llm, enabled=True)
    v = await r.review("code_fix", "x", "output")
    assert v.approved is True and v.ran is False


async def test_bad_json_fails_open():
    r = SecondOpinionReviewer(llm=StubLLM("not json"), enabled=True)
    v = await r.review("code_fix", "x", "output")
    assert v.approved is True and v.ran is False


def test_parse_coerces_stringy_bool():
    v = SecondOpinionReviewer._parse('{"approved": "no", "concern": "risky"}')
    assert v.approved is False
    assert v.concern == "risky"

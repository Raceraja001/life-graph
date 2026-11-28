"""Unit tests for the second-opinion reviewer (fail-closed, 2026-11-28)."""

from __future__ import annotations

import pytest

from life_graph.services.dev.second_opinion import (
    ReviewStatus,
    ReviewVerdict,
    SecondOpinionReviewer,
)


class StubLLM:
    def __init__(self, reply="", raise_exc: BaseException | None = None):
        self.reply = reply
        self.raise_exc = raise_exc
        self.calls = 0

    async def chat(self, messages, **kw):
        self.calls += 1
        if self.raise_exc is not None:
            raise self.raise_exc
        return self.reply


async def test_disabled_is_noop_and_lands_as_before():
    llm = StubLLM('{"approved": false, "concern": "bug"}')
    r = SecondOpinionReviewer(llm=llm, enabled=False)
    v = await r.review("code_fix", "do x", "some output")
    assert v.status is ReviewStatus.SKIPPED
    assert v.approved is True and v.ran is False  # unchanged legacy view
    assert v.may_auto_land and not v.needs_human
    assert llm.calls == 0  # never called the model


async def test_empty_output_is_skipped_without_call():
    llm = StubLLM('{"approved": false}')
    r = SecondOpinionReviewer(llm=llm, enabled=True)
    v = await r.review("code_fix", "do x", "")
    assert v.status is ReviewStatus.SKIPPED
    assert llm.calls == 0


async def test_enabled_without_a_model_is_not_reviewed():
    r = SecondOpinionReviewer(llm=None, enabled=True)
    v = await r.review("code_fix", "do x", "output")
    assert v.status is ReviewStatus.NOT_REVIEWED
    assert v.needs_human and not v.approved and not v.ran


async def test_dissent_blocks():
    llm = StubLLM('{"approved": false, "concern": "SQL injection in query builder"}')
    r = SecondOpinionReviewer(llm=llm, enabled=True)
    v = await r.review("code_fix", "add search", 'def q(s): return f"...{s}"')
    assert v.status is ReviewStatus.OBJECTED
    assert v.ran is True and v.approved is False and v.needs_human
    assert "injection" in v.concern


async def test_approval_passes():
    llm = StubLLM('{"approved": true, "concern": ""}')
    r = SecondOpinionReviewer(llm=llm, enabled=True)
    v = await r.review("code_fix", "x", "clean output")
    assert v.status is ReviewStatus.APPROVED
    assert v.approved is True and v.ran is True and v.may_auto_land
    assert v.concern is None


@pytest.mark.parametrize("exc", [RuntimeError("llm down"), TimeoutError("slow"), ConnectionError()])
async def test_call_error_or_timeout_is_not_reviewed(exc):
    r = SecondOpinionReviewer(llm=StubLLM(raise_exc=exc), enabled=True)
    v = await r.review("code_fix", "x", "output")
    assert v.status is ReviewStatus.NOT_REVIEWED
    assert v.needs_human and not v.may_auto_land and not v.approved
    assert type(exc).__name__ in v.concern  # the reason travels with the verdict


@pytest.mark.parametrize(
    ("reply", "reason"),
    [
        ("not json", "not JSON"),
        (None, "not JSON"),
        ("[true]", "not a JSON object"),
        ('{"concern": ""}', "no 'approved'"),
        ('{"approved": "maybe"}', "unreadable"),
        ('{"approved": null}', "unreadable"),
    ],
)
async def test_unreadable_reply_is_not_reviewed(reply, reason):
    r = SecondOpinionReviewer(llm=StubLLM(reply), enabled=True)
    v = await r.review("code_fix", "x", "output")
    assert v.status is ReviewStatus.NOT_REVIEWED
    assert reason in v.concern
    assert v.needs_human


def test_parse_coerces_stringy_bool():
    v = SecondOpinionReviewer._parse('{"approved": "no", "concern": "risky"}')
    assert v.status is ReviewStatus.OBJECTED
    assert v.concern == "risky"
    assert SecondOpinionReviewer._parse('{"approved": "yes"}').status is ReviewStatus.APPROVED


def test_legacy_keyword_form_maps_onto_statuses():
    assert ReviewVerdict(approved=True, ran=True).status is ReviewStatus.APPROVED
    assert ReviewVerdict(approved=False, ran=True).status is ReviewStatus.OBJECTED
    assert ReviewVerdict(approved=True, ran=False).status is ReviewStatus.SKIPPED
    assert ReviewVerdict(approved=False, ran=False).status is ReviewStatus.NOT_REVIEWED
    with pytest.raises(TypeError):
        ReviewVerdict()


def test_only_approved_and_skipped_may_auto_land():
    may = {s for s in ReviewStatus if ReviewVerdict(status=s).may_auto_land}
    assert may == {ReviewStatus.APPROVED, ReviewStatus.SKIPPED}


def test_the_old_gate_alone_would_let_not_reviewed_through():
    """Why the dispatcher must gate on needs_human, not ``ran and not approved``."""
    v = ReviewVerdict.not_reviewed("timeout")
    old_gate_blocks = v.ran and not v.approved
    assert old_gate_blocks is False
    assert v.needs_human is True

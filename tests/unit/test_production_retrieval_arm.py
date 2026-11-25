"""Pure parts of the production-path arm (M3): no database needed."""

from __future__ import annotations

import asyncio
import math

import pytest

from life_graph import runtime
from life_graph.config import settings
from life_graph.evals import production_retrieval_arm as arm
from life_graph.services.memory import retrieval


def test_fake_embedding_is_deterministic_unit_and_sized():
    a = arm.fake_embedding("I live in Chennai.")
    assert a == arm.fake_embedding("I live in Chennai.")
    assert len(a) == settings.embedding_dimension
    assert math.isclose(math.sqrt(sum(v * v for v in a)), 1.0, rel_tol=1e-9)


def test_fake_embedding_puts_shared_words_closer():
    def cos(x, y):
        return sum(p * q for p, q in zip(x, y, strict=True))

    q = arm.fake_embedding("Where do I live?")
    near = arm.fake_embedding("I live in Chennai.")
    far = arm.fake_embedding("Our dog eats biscuits.")
    assert cos(q, near) > cos(q, far)


def test_cleanup_refuses_a_real_tenant():
    with pytest.raises(ValueError, match="non-throwaway"):
        asyncio.run(arm.cleanup_tenant("owner"))


def test_new_tenants_are_throwaway_and_unique():
    a, b = arm.new_tenant(), arm.new_tenant()
    assert a != b
    assert a.startswith(arm.TENANT_PREFIX) and b.startswith(arm.TENANT_PREFIX)


@pytest.mark.asyncio
async def test_production_fakes_disable_the_judge_and_the_model_embedder():

    real_judge = retrieval.judge
    with arm.production_fakes():
        assert await retrieval.judge("q", ["a"]) is None
        vec = await runtime.get_memory_manager().generate_embedding("hello")
        assert vec == arm.fake_embedding("hello")
    assert retrieval.judge is real_judge


def test_abstention_indicator_arithmetic():
    out = arm._abstention([(True, True), (True, False), (False, True), (False, False)])
    assert out == {"flagged": 2, "abstain_questions": 2, "precision": 0.5, "recall": 0.5}

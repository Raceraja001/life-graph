"""run_chain runs verifiers concurrently, but must still return results in
chain order (several callers index results[i] against chain[i]) and must
not let one slow/failing verifier distort another's outcome.
"""

from __future__ import annotations

import asyncio
import time

import pytest

from life_graph.services.verifiers import VerifierChain, VerifierResult


@pytest.fixture
def chain():
    return VerifierChain()


async def _slow_pass(_workdir, _ctx):
    await asyncio.sleep(0.2)
    return True, {"note": "slow"}


async def _fast_fail(_workdir, _ctx):
    return False, {"note": "fast"}


async def _raises(_workdir, _ctx):
    raise RuntimeError("boom")


async def _inconclusive(_workdir, _ctx):
    return None, {"note": "no tool"}


@pytest.mark.asyncio
async def test_results_preserve_chain_order_regardless_of_completion_order(chain):
    chain.register("slow", _slow_pass)
    chain.register("fast", _fast_fail)

    results = await chain.run_chain(["slow", "fast"], None, {})

    assert [r.verifier for r in results] == ["slow", "fast"]
    assert results[0].passed is True
    assert results[1].passed is False


@pytest.mark.asyncio
async def test_actually_runs_concurrently_not_sequentially(chain):
    chain.register("a", _slow_pass)
    chain.register("b", _slow_pass)
    chain.register("c", _slow_pass)

    start = time.monotonic()
    await chain.run_chain(["a", "b", "c"], None, {})
    elapsed = time.monotonic() - start

    # Sequential would take ~0.6s (3 * 0.2s); concurrent should finish in
    # roughly one sleep's worth. Generous margin for CI jitter.
    assert elapsed < 0.4


@pytest.mark.asyncio
async def test_one_verifier_raising_does_not_affect_another(chain):
    chain.register("broken", _raises)
    chain.register("fine", _slow_pass)

    results = await chain.run_chain(["broken", "fine"], None, {})

    assert results[0] == VerifierResult("broken", False, {"error": "boom"})
    assert results[1].passed is True


@pytest.mark.asyncio
async def test_unknown_verifier_and_inconclusive_still_work_concurrently(chain):
    chain.register("real", _inconclusive)

    results = await chain.run_chain(["nope", "real"], None, {})

    assert results[0] == VerifierResult(
        "nope", False, {"error": "Unknown verifier: nope"}
    )
    assert results[1].inconclusive is True
    assert results[1].passed is False

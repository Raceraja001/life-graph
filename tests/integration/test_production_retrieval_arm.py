"""The production-path arm of the memory lab, against a real Postgres (M3).

Runs a slice of the tuning split through hybrid_search and retrieve() with the
fake embedder and the judge disabled, and checks that the throwaway tenant
leaves nothing behind. The full baseline comes from
scripts/eval_production_retrieval.py; this only keeps the harness working.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from life_graph.evals import memory_benchmark as lab
from life_graph.evals.production_retrieval_arm import (
    ARMS,
    PRECISION_KS,
    _tenant_tables,
    evaluate_split_production,
)
from life_graph.storage.database import async_session
from tests.integration.conftest import skip_on_db_error


@pytest.mark.asyncio
@skip_on_db_error
async def test_production_arm_scores_a_slice_and_cleans_up():
    split = await evaluate_split_production("tuning_dev", lab.TUNING_DATASET, max_questions=15)

    assert split["memories_seeded"] == 93
    assert split["question_count"] == 15
    assert split["memories_left_after_cleanup"] == 0
    assert set(split["arms"]) == set(ARMS)
    for arm in ARMS:
        rep = split["arms"][arm]
        ov = rep["overall"]
        assert rep["unmapped_results"] == 0, arm
        for key in ("recall_at_1", "recall_at_5", "mrr", "ndcg_at_5", "full_support_at_5"):
            assert 0.0 <= ov[key] <= 1.0, (arm, key)
        for k in PRECISION_KS:
            assert 0.0 <= ov[f"precision_at_{k}"] <= 1.0
        # The first questions are simple lookups ("What is my name?"); a
        # working store finds most of them even with the hashing embedder.
        assert ov["recall_at_5"] >= 0.5, arm
        assert rep["latency_ms"]["count"] == 15

    # Nothing of any throwaway tenant is left in any tenant-scoped table.
    async with async_session() as s:
        for table in await _tenant_tables():
            left = await s.scalar(
                text(f"SELECT count(*) FROM \"{table}\" WHERE tenant_id LIKE 'm3eval\\_%'")
            )
            assert left == 0, table

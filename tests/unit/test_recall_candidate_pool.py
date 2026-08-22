"""Proactive recall's candidate pool is chosen by value, not by age.

_retrieve_candidates used list_memories(), which orders by created_at DESC.
The pool was therefore "the newest N memories": on the database this was
written against, 61% of one tenant's active memories could never be surfaced
however important they were, and the ranker only ever re-sorted an arbitrary
slice. Surfacing is also what refreshes last_accessed, so memories outside
the window could never be reinforced either -- they aged toward the removal
horizon no matter what they were worth.

list_recall_candidates() ranks in SQL instead. Its weights have to track
scoring/ranking.py or the pre-filter would optimise for something the ranker
does not.
"""

import ast
import pathlib

import pytest
from sqlalchemy.dialects import postgresql

from life_graph.scoring import ranking
from life_graph.scoring.ranking import RecallRanker

ROOT = pathlib.Path(__file__).resolve().parents[2]
POSTGRES_PY = ROOT / "life_graph" / "storage" / "postgres.py"
RECALL_PY = ROOT / "life_graph" / "services" / "recall.py"


def _base_score_coefficients() -> dict[str, float]:
    """Column -> weight, read out of the base_score expression in the store."""
    tree = ast.parse(POSTGRES_PY.read_text())
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Assign)
            and node.targets
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == "base_score"
        ):
            continue
        coeffs: dict[str, float] = {}
        for sub in ast.walk(node.value):
            if (
                isinstance(sub, ast.BinOp)
                and isinstance(sub.op, ast.Mult)
                and isinstance(sub.left, ast.Constant)
                and isinstance(sub.right, ast.Attribute)
                and isinstance(sub.right.value, ast.Name)
                and sub.right.value.id == "Memory"
            ):
                coeffs[sub.right.attr] = float(sub.left.value)
        return coeffs
    raise AssertionError("postgres.py has no base_score expression")


def test_sql_prefilter_weights_match_the_ranker():
    """A pre-filter optimising for different weights selects the wrong pool."""
    coeffs = _base_score_coefficients()
    assert coeffs["importance"] == ranking._WEIGHT_IMPORTANCE
    assert coeffs["impact_score"] == ranking._WEIGHT_IMPACT
    assert coeffs["trust_score"] == ranking._WEIGHT_TRUST


def test_recall_no_longer_pages_by_creation_date():
    """Regression: the pool must not be `the newest N`."""
    src = ast.parse(RECALL_PY.read_text())
    for node in ast.walk(src):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "_retrieve_candidates":
            calls = {
                n.func.attr
                for n in ast.walk(node)
                if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            }
            assert "list_recall_candidates" in calls
            assert "list_memories" not in calls, (
                "list_memories() orders by created_at DESC, which makes the "
                "candidate pool the newest N memories"
            )
            return
    raise AssertionError("recall.py has no _retrieve_candidates()")


@pytest.mark.asyncio
async def test_candidate_query_is_tenant_scoped_and_value_ordered():
    from life_graph.core.tenant import set_tenant_context
    from life_graph.storage.postgres import PostgresMemoryStore

    set_tenant_context("pool-test-tenant")
    store = PostgresMemoryStore()

    captured: dict = {}

    class _FakeResult:
        def scalars(self):
            class _S:
                def all(self_inner):
                    return []

            return _S()

    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def execute(self, stmt):
            captured["stmt"] = stmt
            return _FakeResult()

    import life_graph.storage.postgres as pg

    original = pg.async_session
    pg.async_session = lambda: _FakeSession()
    try:
        await store.list_recall_candidates(filters={"status": "active"}, limit=50)
    finally:
        pg.async_session = original

    sql = str(
        captured["stmt"].compile(
            dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
        )
    )
    assert "memories.tenant_id = 'pool-test-tenant'" in sql
    order_by = sql.split("ORDER BY", 1)[1]
    # created_at may appear only as a tie-break, never as the leading term.
    leading = order_by.split(",")[0]
    assert "created_at" not in leading, f"pool still ordered by age: {leading.strip()}"
    for col in ("importance", "impact_score", "trust_score", "access_count"):
        assert col in order_by, f"{col} missing from the pre-filter ordering"


def test_rerank_returns_what_was_asked_for():
    """Regression: the type rule truncated 5 requested results to 3."""
    ranker = RecallRanker()
    cands = [
        {"id": str(i), "tags": [f"topic{i}"], "final_score": 0.9 - i * 0.01} for i in range(10)
    ]
    assert len(ranker.rerank(cands, max_results=5)) == 5


def test_rerank_never_invents_results():
    ranker = RecallRanker()
    cands = [{"id": "a", "tags": ["x"], "final_score": 0.9}]
    assert len(ranker.rerank(cands, max_results=5)) == 1


def test_type_diversity_is_still_a_preference():
    """Lower-scoring types get promoted once one type hits its soft cap."""
    ranker = RecallRanker()
    cands = [
        {"id": f"A{i}", "tags": [f"t{i}"], "source_type": "A", "final_score": 0.9 - i * 0.01}
        for i in range(6)
    ] + [
        {"id": f"B{i}", "tags": [f"u{i}"], "source_type": "B", "final_score": 0.5 - i * 0.01}
        for i in range(2)
    ]
    out = ranker.rerank(cands, max_results=5)
    types = [c["source_type"] for c in out]
    assert types.count("A") == ranking._MAX_PER_TYPE
    assert types.count("B") == 2


def test_topic_cap_is_still_a_hard_limit():
    """Unlike type, the topic cap is documented as a cap and stays one."""
    ranker = RecallRanker()
    cands = [
        {"id": str(i), "tags": ["same"], "source_type": f"s{i}", "final_score": 0.9 - i * 0.01}
        for i in range(10)
    ]
    assert len(ranker.rerank(cands, max_results=5, max_per_topic=2)) == 2

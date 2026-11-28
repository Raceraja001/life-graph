"""The context quality eval (scripts/eval_context_quality.py) on a subset, against Postgres.

Runs the hashing arm over a handful of questions -- current job (supersession),
emergency fund (pending contradiction), salary in March (as_of), credit score
(nothing to find), the injected billing notice, and O6 (change detection
against an earlier turn's trace) -- and checks the harness itself: the
zero-tolerance counts are zero, every throwaway row is gone, and each question
is scored. The full run and its committed baseline are the CI step
"Verify Context Quality Gates".

The numbers it pins are the ones the shipped code gets right today
(supersession and contradiction pairs, the as_of employer); the weak ones
(abstention, deadlines, relationships, E2) are reported by the script and are
not pinned here, so fixing them never breaks this test.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from tests.integration.conftest import skip_on_db_error

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "eval_context_quality.py"
_spec = importlib.util.spec_from_file_location("eval_context_quality", _PATH)
ecq = importlib.util.module_from_spec(_spec)
sys.modules["eval_context_quality"] = ecq
_spec.loader.exec_module(ecq)

SUBSET = {"B1", "C3", "E1", "E2", "G3", "G6", "O6"}


@pytest.mark.asyncio
@skip_on_db_error
async def test_hashing_arm_on_a_subset_scores_and_cleans_up():
    data, gq = ecq.load()
    report = await ecq.run_arm("hashing", data, gq, repeat=2, only=SUBSET)

    zero = report["zero_tolerance"]
    assert zero == {
        "cross_tenant_leaks": 0,
        "cloud_model_calls": 0,
        "forbidden_as_current": 0,
        "rows_left_after_cleanup": 0,
    }
    assert set(report["per_question"]) == SUBSET
    per_q = report["per_question"]
    # Supersession and a pending contradiction are shown with both sides.
    assert per_q["B1"]["conflicts_found"] == per_q["B1"]["conflicts_expected"] == 1
    assert per_q["C3"]["conflicts_found"] == per_q["C3"]["conflicts_expected"] == 1
    # The ended employer is current as of 2019, and only that.
    assert per_q["E1"]["found_required"] == 1
    assert per_q["E1"]["forbidden_as_current"] == []
    # The outside notice is labelled as outside, never as the owner's word.
    assert per_q["G6"]["injection_mislabelled"] == []
    assert per_q["G6"]["field_wrong"] == []
    # O6 ran the Stage 2 path against the earlier turn's trace.
    changes = report["change_detection"]
    assert changes is not None and changes["insufficient"] is False
    assert changes["expected"] == len(data["change_scenario"]["expect_changes"])
    for cat, entry in report["by_category"].items():
        assert entry["questions"] >= 1, cat
        assert entry["provenance_coverage"] in (None, 1.0), cat


@pytest.mark.asyncio
async def test_the_model_guard_refuses_cloud_routes():
    from life_graph import runtime
    from life_graph.services.llm.client import LMStudioClient

    calls: dict[str, int] = {}
    with ecq.model_guard(calls):
        with pytest.raises(RuntimeError):
            runtime.get_resilient_llm()
        with pytest.raises(RuntimeError):
            LMStudioClient()
    assert calls == {"resilient_chain": 1, "chat_client": 1}
    # Restored afterwards.
    assert LMStudioClient() is not None


INGEST_SUBSET = {"B1", "C3", "O5", "D2", "O6"}


@pytest.mark.asyncio
@skip_on_db_error
async def test_ingest_arm_builds_the_world_through_the_save_path_and_cleans_up():
    """The ingest arm (scripts/context_quality_ingest.py): no leaks, no model call,
    nothing left behind, usable fixtures, and its ingestion report filled in.
    What it gets right is not pinned here: that is the arm's baseline."""
    data, gq = ecq.load()
    report = await ecq.run_arm("ingest", data, gq, repeat=2, only=INGEST_SUBSET)

    zero = report["zero_tolerance"]
    assert zero["cross_tenant_leaks"] == 0
    assert zero["cloud_model_calls"] == 0
    assert zero["rows_left_after_cleanup"] == 0
    assert report["fixtures"]["problems"] == []
    assert set(report["per_question"]) == INGEST_SUBSET
    ing = report["ingestion"]
    assert ing["memories"] > 0 and ing["replay_misses"] == []
    assert ing["owner_actions_failed"] == []
    assert report["change_detection"] is not None

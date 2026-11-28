"""The ingest arm's fixtures loader and its pure helpers (scripts/context_quality_ingest.py),
and the ingest parts of scripts/eval_context_quality.py's baseline and gate.

No DB: the arm itself runs in CI ("Verify Context Quality Gates") and in
tests/integration.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import context_quality_ingest as ci  # noqa: E402

_PATH = ROOT / "scripts" / "eval_context_quality.py"
_spec = importlib.util.spec_from_file_location("eval_context_quality", _PATH)
ecq = importlib.util.module_from_spec(_spec)
sys.modules["eval_context_quality"] = ecq
_spec.loader.exec_module(ecq)

DATA = json.loads((ROOT / "evals" / "context_quality" / "dataset.json").read_text(encoding="utf-8"))
FX = ci.load_fixtures()


def test_the_committed_fixtures_fit_the_dataset():
    assert ci.check_fixtures(FX, DATA) == []
    cov = ci.coverage(FX, DATA)
    assert cov["no_message"] == []  # every memory and decision has its message
    langs = {m["lang"] for m in FX["messages"]}
    assert {"en", "ta", "tanglish"} <= langs
    assert FX["recorded"]["anchor"]


def test_every_recorded_answer_is_the_extractor_schema():
    for m in FX["messages"]:
        if m["path"] == "memory_save":
            continue
        for item in ci.raw_facts(m):
            assert isinstance(item, dict) and item.get("content"), m["id"]


def _broken(mutate):
    fx = copy.deepcopy(FX)
    mutate(fx)
    return ci.check_fixtures(fx, DATA)


def test_check_fixtures_finds_each_kind_of_problem():
    def dup_key(fx):
        fx["messages"][1]["expect"] = list(fx["messages"][0]["expect"])

    def bad_path(fx):
        fx["messages"][0]["path"] = "telepathy"

    def no_raw(fx):
        msg = next(m for m in fx["messages"] if m["path"] == "capture")
        msg["raw"] = None

    def short_keys(fx):
        msg = next(m for m in fx["messages"] if m["path"] == "capture")
        msg["keys"] = msg["keys"] + [None]

    def bad_action(fx):
        fx["owner_actions"].append({"op": "confirm", "key": "d_nope", "at_d": -1})

    def future(fx):
        fx["messages"][0]["said_d"] = 3

    for mutate, word in (
        (dup_key, "already said"),
        (bad_path, "path"),
        (no_raw, "no recorded raw"),
        (short_keys, "label each"),
        (bad_action, "not a dataset record"),
        (future, "said_d"),
    ):
        problems = _broken(mutate)
        assert any(word in p for p in problems), (word, problems)


def test_fact_keys_maps_recorded_content_and_memory_saves():
    capture = {
        "path": "capture",
        "raw": json.dumps({"facts": [{"content": " A  fact. "}, {"content": "Other."}]}),
        "keys": ["k1", None],
    }
    assert ci.fact_keys(capture) == {"a fact.": "k1"}
    save = {"path": "memory_save", "save": "Saved words.", "expect": ["k2"]}
    assert ci.fact_keys(save) == {"saved words.": "k2"}


def test_shift_dates_moves_only_the_models_iso_days():
    raw = json.dumps(
        {"facts": [{"content": "c", "valid_until": "2026-11-20", "valid_from": "soon"}]}
    )
    out = json.loads(ci.shift_dates(raw, 10))["facts"][0]
    assert out["valid_until"] == "2026-11-30" and out["valid_from"] == "soon"
    assert ci.shift_dates(raw, 0) == raw


def test_shift_of_counts_days_from_the_recording():
    fx = {"recorded": {"anchor": "2026-11-28"}}
    assert ci.shift_of(fx, datetime(2026, 12, 8, 5, tzinfo=UTC)) == 10
    assert ci.shift_of({}, datetime(2026, 12, 8, tzinfo=UTC)) == 0


def test_plan_sends_the_messages_of_the_spec_oldest_first_at_overridden_times():
    fx = {
        "messages": [
            {"id": "b", "said_d": -5, "expect": ["k2"]},
            {"id": "a", "said_d": -9, "expect": ["k1"]},
            {"id": "c", "said_d": -1, "expect": ["k3"]},
            {"id": "d", "said_d": -2, "expect": [], "decision": "d1"},
        ]
    }
    got = ci.plan(fx, {"k1": -9, "k2": -0.5, "d1": -2})
    assert [(m["id"], m["at_d"]) for m in got] == [("a", -9), ("d", -2), ("b", -0.5)]


def test_owner_actions_wait_for_their_records_and_never_precede_them():
    fx = {
        "owner_actions": [
            {"op": "confirm", "key": "d1", "at_d": -10},
            {"op": "supersede", "key": "d1", "by": "d2", "at_d": -10},
        ]
    }
    assert [i for i, _, _ in ci.owner_actions_due(fx, {"d1"}, set(), {"d1": -12})] == [0]
    due = ci.owner_actions_due(fx, {"d1", "d2"}, {0}, {"d1": -12, "d2": -3})
    assert [(i, at) for i, _, at in due] == [(1, -3)]


def test_auto_keys_labels_the_best_matching_fact_only():
    raw = json.dumps(
        {
            "facts": [
                {"content": "Amma has type 2 diabetes."},
                {"content": "The owner refills Amma's insulin every second Saturday."},
            ]
        }
    )
    gold = {
        "k": "The owner refills Kamala's insulin and takes her to the clinic every second Saturday."
    }
    assert ci.auto_keys(raw, ["k"], gold) == [None, "k"]
    assert ci.auto_keys(raw, ["k"], {"k": "Something unrelated entirely."}) == [None, None]


def test_flags_on_turns_the_four_flags_on_and_back():
    from life_graph.config import settings

    before = {f: getattr(settings, f) for f in ci.FLAGS}
    with ci.flags_on():
        assert all(getattr(settings, f) for f in ci.FLAGS)
    assert {f: getattr(settings, f) for f in ci.FLAGS} == before


def test_the_replay_extractor_parses_the_recording_and_counts_a_miss():
    import asyncio

    msg = next(m for m in FX["messages"] if m["id"] == "m_promotion")
    ext = ci._replay_class()({msg["said"]: msg["raw"]})
    facts = asyncio.run(ext._extract_local(msg["said"]))
    assert [f.slot for f in facts] == ["work.title", "work.salary"]
    assert asyncio.run(ext._extract_local("never recorded")) == []
    assert ext.misses == ["never recorded"] and ext.replayed == 1


# ── eval_context_quality: the ingest baseline and gate ───────


def _arm(forbidden=0, leaks=0, problems=(), precision=0.5):
    return {
        "by_category": {"A": {"precision": precision, "denominators": {"precision": 40}}},
        "zero_tolerance": {
            "cross_tenant_leaks": leaks,
            "cloud_model_calls": 0,
            "forbidden_as_current": forbidden,
            "rows_left_after_cleanup": 0,
        },
        "fixtures": {"problems": list(problems)},
    }


def test_baseline_of_writes_the_arms_that_ran_and_keeps_the_others():
    previous = {"about": "old", "arm": "hashing", "by_category": {"A": {"precision": 0.9}}}
    out = ecq.baseline_of({"arms": {"ingest": _arm(forbidden=3)}}, previous)
    assert out["by_category"] == {"A": {"precision": 0.9}}  # hashing floors untouched
    assert out["ingest"]["by_category"] == {"A": {"precision": 0.5}}
    assert out["ingest"]["forbidden_as_current_max"] == 3


def test_the_ingest_gate_before_and_after_its_baseline():
    assert ecq.ingest_regressions(_arm(forbidden=7), None) == []
    assert ecq.ingest_regressions(_arm(leaks=1), None) == [
        "ingest: cross_tenant_leaks = 1 (target 0)"
    ]
    assert ecq.ingest_regressions(_arm(problems=["m1: x"]), None) == ["ingest: fixtures: m1: x"]
    floors = {"by_category": {"A": {"precision": 0.7}}, "forbidden_as_current_max": 2}
    fails = ecq.ingest_regressions(_arm(forbidden=3, precision=0.5), floors)
    assert any("A.precision" in f for f in fails)
    assert any("forbidden_as_current = 3 > baseline 2" in f for f in fails)

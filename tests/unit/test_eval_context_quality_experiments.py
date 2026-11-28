"""scripts/eval_context_quality.py: the experiment flags, the split and the item log.

No database: only the pure parts (flag parsing, the split, scoring rows).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from life_graph.services.memory import snapshot_experiments as xp

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_PATH = ROOT / "scripts" / "eval_context_quality.py"
_spec = importlib.util.spec_from_file_location("eval_context_quality", _PATH)
ecq = importlib.util.module_from_spec(_spec)
sys.modules["eval_context_quality"] = ecq
_spec.loader.exec_module(ecq)

QUESTIONS = json.loads((ROOT / "evals" / "context_quality" / "questions.json").read_text())


def _args(**kw) -> argparse.Namespace:
    base = {"mode": "", "experiments": "", "xp_set": [], "max_items": None, "split": None}
    base.update(kw)
    return argparse.Namespace(**base)


def test_no_flags_change_nothing():
    assert ecq.experiment_run(_args()) == ({}, {})


def test_experiments_are_recorded_with_their_constants():
    record, kw = ecq.experiment_run(
        _args(experiments="f,B", xp_set=["cosine_floor=0.75"], max_items=12, split="tune")
    )
    assert record["experiments"] == ["B", "F"]
    assert record["experiment_names"] == ["budget", "query_type"]
    assert record["xp_set"] == {"COSINE_FLOOR": 0.75}
    assert record["constants"]["COSINE_FLOOR"] == 0.75
    assert record["max_items"] == 12 and record["split"] == "tune"
    assert kw["experiments"] == {"budget", "query_type"} and kw["budget"].max_items == 12
    # The value travels with the call; the module's constant is untouched.
    assert kw["tunables"].cosine_floor == 0.75 and xp.COSINE_FLOOR == 0.8
    assert record["constants"] == {**xp.DEFAULT_TUNABLES.named(), "COSINE_FLOOR": 0.75}


def test_xp_set_casts_like_before_and_an_int_takes_a_float_spelling():
    record, kw = ecq.experiment_run(_args(experiments="F", xp_set=["MIN_KEEP=4.0"]))
    assert record["xp_set"] == {"MIN_KEEP": 4} and isinstance(kw["tunables"].min_keep, int)
    with pytest.raises(SystemExit):
        ecq.experiment_run(_args(experiments="F", xp_set=["COSINE_FLOOR=abc"]))


def test_mode_alone_runs_the_production_path():
    record, kw = ecq.experiment_run(_args(mode="recall"))
    assert kw == {"mode": "recall"}
    assert record["mode"] == "recall"
    assert record["experiments"] == ["B", "C", "F", "H", "I", "J", "K"]
    assert record["constants"]["COSINE_FLOOR"] == 0.70
    assert "xp_set" not in record


def test_mode_plus_flags_starts_from_the_mode():
    record, kw = ecq.experiment_run(
        _args(mode="precision", experiments="A", xp_set=["COSINE_FLOOR=0.8"])
    )
    assert "mode" not in kw and record["mode"] == "precision"
    assert kw["experiments"] == {"rank"} | xp.MODES["precision"].experiments
    assert kw["tunables"] == xp.MODES["precision"].tunables.with_values({"COSINE_FLOOR": 0.8})
    assert record["xp_set"] == {"COSINE_FLOOR": 0.8}


@pytest.mark.parametrize("bad", ["NOPE=1", "COSINE_FLOOR", "COSINE_FLOOR="])
def test_an_unknown_constant_is_refused(bad):
    with pytest.raises(SystemExit):
        ecq.experiment_run(_args(xp_set=[bad]))


def test_the_split_is_stable_and_cuts_every_category_roughly_in_half():
    ids = [q["id"] for q in QUESTIONS["questions"]]
    first = {i: ecq.question_split(i) for i in ids}
    assert first == {i: ecq.question_split(i) for i in ids}
    tune = [i for i, s in first.items() if s == "tune"]
    assert 0.3 < len(tune) / len(ids) < 0.7


def test_rows_log_each_item_and_count_the_standing_block():
    ids = {"m1": "a", "d1": "b", "i1": "c"}

    def item(rid, kind, reason, score):
        return SimpleNamespace(
            source_ref=SimpleNamespace(id=rid, kind=kind), reason=reason, score=score
        )

    snap = SimpleNamespace(
        items=[
            item("m1", "memory", "search_hit", 0.9),
            item("d1", "decision", "current_decision", 0.21),
            item("i1", "intention", "due_intention", 0.22),
        ]
    )
    log = ecq._item_log(snap, ids)
    assert log[0] == {
        "key": "a",
        "kind": "memory",
        "reason": "search_hit",
        "score": 0.9,
        "block": "search",
    }
    assert [e["block"] for e in log] == ["search", "standing", "standing"]
    assert not any("content" in e for e in log)
    rows = [{"items": 3, "ok_items": 2, "standing_items": 2, "ok_standing": 1, "required": 1}]
    rows[0].update(
        {k: [] for k in ("forbidden_as_current", "noise", "leaks", "injection_mislabelled")}
    )
    summary = ecq.summarise(rows)
    assert summary["precision"] == round(2 / 3, 4)
    assert summary["precision_without_standing"] == 1.0
    assert summary["standing_items"] == 2


def test_the_lookup_embedder_knows_the_texts_the_experiments_embed():
    data, gq = ecq.load()
    texts = set(ecq._all_texts(data, gq))
    assert set(xp.HUB_PROBES) <= texts  # G
    assert {i["content"] for i in data["intentions"]} <= texts  # H


def test_the_new_letters_reach_the_eval():
    record, kw = ecq.experiment_run(_args(mode="recall", experiments="H,I,J,K"))
    assert record["experiments"] == ["B", "C", "F", "H", "I", "J", "K"]
    assert kw["tunables"] == xp.MODES["recall"].tunables

"""scripts/eval_ingestion_structure.py: its scoring, and the committed cases against today's code.

ADR docs/design/adr-m8-ingestion-structure.md §6.1. No DB, no model.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest

_PATH = Path(__file__).resolve().parents[2] / "scripts" / "eval_ingestion_structure.py"
_spec = importlib.util.spec_from_file_location("eval_ingestion_structure", _PATH)
eis = importlib.util.module_from_spec(_spec)
sys.modules["eval_ingestion_structure"] = eis
_spec.loader.exec_module(eis)

NOW = datetime(2026, 11, 28, 9, 30, tzinfo=UTC)


@pytest.fixture(scope="module")
def report():
    return asyncio.run(eis.evaluate(eis.load(), NOW))


def test_the_committed_cases_hold_every_zero_tolerance_count(report):
    assert report["zero_tolerance"] == dict.fromkeys(report["zero_tolerance"], 0)


def test_the_cases_cover_each_structure_and_tamil(report):
    data = eis.load()
    assert len(data["supersession"]) >= 30 and len(data["links"]) >= 12
    assert len(data["decisions"]) >= 30
    assert report["tamil_or_tanglish_share"] >= 0.25
    for name in ("supersession", "links", "decisions"):
        langs = {c["lang"] for c in data[name]}
        assert {"ta", "tanglish"} & langs, name


def test_the_committed_baseline_holds(report):
    import json

    base = json.loads(eis.BASELINE_PATH.read_text(encoding="utf-8"))
    assert eis.regressions(report, base) == []


# ── The scoring itself ───────────────────────────────────────


def _sup(id_, *, tier, same, trust="self", correction=False, category="s1", end=False):
    case = {
        "id": id_,
        "category": category,
        "trust_tier": trust,
        "new": {"content": "x", **({"correction": True} if correction else {})},
        "gold": {"same_attribute": same, "tier": "high", "world_end": False},
    }
    return case, {"tier": tier, "world_end": end}


def test_an_auto_supersede_of_another_attribute_is_counted():
    s = eis.score_supersession(
        [_sup("a", tier="high", same=False), _sup("b", tier="medium", same=False)]
    )
    assert s["wrong_auto_supersede"] == ["a"]
    assert s["precision"] == 0.0


def test_outside_text_applying_or_filing_low_is_counted_but_waiting_is_not():
    rows = [
        _sup("hi", tier="high", same=True, trust="external"),
        _sup("lo", tier="low", same=True, trust="hostile_possible"),
        _sup("med", tier="medium", same=True, trust="external"),
    ]
    assert eis.score_supersession(rows)["outside"] == ["hi", "lo"]


def test_a_correction_with_an_end_is_counted():
    s = eis.score_supersession([_sup("c", tier="high", same=True, correction=True, end=True)])
    assert s["correction_given_valid_until"] == ["c"]


def test_a_decision_confirmed_with_no_owner_step_is_counted():
    case = {
        "id": "m",
        "steps": [{"actor": "service_key", "via": "route", "to": "decided"}],
        "gold": {"final": "candidate", "confirmed": False},
    }
    owner = {**case, "id": "o", "steps": [{"actor": "owner", "via": "route", "to": "decided"}]}
    d = eis.score_decisions(
        [],
        [
            (case, {"final": "decided", "confirmed": False}),
            (owner, {"final": "decided", "confirmed": True}),
        ],
    )
    assert d["confirmed_without_owner"] == ["m"]


def test_a_capture_candidate_from_outside_is_counted():
    caps = [({"id": "e", "surface": "email", "gold": {"candidates": 0}}, 1)]
    assert eis.score_decisions(caps, [])["outside"] == ["e"]


def test_links_touching_an_earlier_owner_memory_are_counted():
    case = {"id": "x", "gold": []}
    out = eis.score_links([(case, {"links": [(0, 1, "BECAUSE")], "touch_owner": 1})])
    assert out["outside"] == ["x"]
    assert out["because_precision"] == 0.0


def test_regressions_flag_a_zero_count_and_a_fall_below_the_floor():
    rep = {
        "zero_tolerance": {"wrong_auto_supersede": 1},
        "supersession": {"recall": 0.5, "denominators": {"recall": 40}},
    }
    fails = eis.regressions(rep, {"supersession": {"recall": 0.8}})
    assert any("wrong_auto_supersede" in f for f in fails)
    assert any("supersession.recall" in f for f in fails)
    ok = {
        "zero_tolerance": {"x": 0},
        "supersession": {"recall": 0.78, "denominators": {"recall": 40}},
    }
    assert eis.regressions(ok, {"supersession": {"recall": 0.8}}) == []


# ── The harness runs the real save-path rules ────────────────


def _case(**kw):
    base = {
        "id": "t",
        "category": "s1",
        "old": {"content": "The owner lives in Madurai.", "slot": "home.city"},
        "new": {
            "content": "The owner moved to Coimbatore last month.",
            "fact_type": "fact",
            "confidence": 0.95,
            "slot": "home.city",
        },
        "trust_tier": "self",
        "similarity": 0.7,
    }
    base.update(kw)
    return base


def _run(case):
    async def go():
        with eis.flags_on():
            return await eis.run_supersession_case(case, NOW)

    return asyncio.run(go())


def test_the_owners_firm_slot_change_is_applied_with_a_world_end():
    assert _run(_case()) == {"tier": "high", "world_end": True}


def test_the_same_slot_from_outside_text_only_waits():
    assert _run(_case(trust_tier="external"))["tier"] == "medium"


def test_a_correction_is_applied_without_a_world_end():
    new = {**_case()["new"], "correction": True}
    assert _run(_case(new=new)) == {"tier": "high", "world_end": False}


def test_a_service_key_cannot_confirm_a_decision():
    case = {"steps": [{"actor": "service_key", "via": "route", "to": "decided"}]}
    out = asyncio.run(eis.run_moves_case(case, NOW))
    assert out == {"final": "candidate", "confirmed": False, "refused": 1}


def test_an_auto_kept_memory_review_confirms_nothing_but_the_owners_does():
    auto = {"steps": [{"actor": "auto_keep", "via": "memory_review", "to": "decided"}]}
    owner = {"steps": [{"actor": "owner", "via": "memory_review", "to": "decided"}]}
    with eis.flags_on():  # the memory side of the lifecycle is behind decision_lifecycle
        assert asyncio.run(eis.run_moves_case(auto, NOW))["final"] == "candidate"
        assert asyncio.run(eis.run_moves_case(owner, NOW))["confirmed"] is True


def test_outside_capture_makes_no_candidate():
    assert (
        eis.run_capture_case({"surface": "email", "text": "We decided to move the meeting."}) == 0
    )
    assert eis.run_capture_case({"surface": "chat", "text": "We decided to move the meeting."}) == 1

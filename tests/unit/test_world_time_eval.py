"""The world-time cases in evals/ingestion_structure/cases.json meet the ADR targets.

ADR docs/design/adr-m8-ingestion-structure.md §6.1: precision >= 0.95 when a
start is set, recall >= 0.85 when the gold has one, and zero tolerance for a
start where the gold is unknown or the phrase is in the future. At least a
quarter of the cases are Tamil or Tanglish.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from life_graph.extraction.world_time import world_time_of

CASES = Path(__file__).resolve().parents[2] / "evals" / "ingestion_structure" / "cases.json"
DATA = json.loads(CASES.read_text(encoding="utf-8"))
TZ = ZoneInfo(DATA["tz"])
TARGETS = DATA["targets"]


def _predict(case: dict) -> tuple[str, str] | None:
    anchor = datetime.fromisoformat(case.get("said_at") or DATA["anchor"])
    found = world_time_of(case["content"], case.get("source_text"), anchor, TZ)
    if found is None:
        return None
    assert found.start.tzinfo is not None
    return found.start.date().isoformat(), found.precision


def _gold(case: dict) -> tuple[str, str] | None:
    want = case["expect"]
    return (
        None if want is None else (date.fromisoformat(want["start"]).isoformat(), want["precision"])
    )


def _scores() -> dict:
    cases = DATA["world_time"]
    predicted = [(c, _predict(c), _gold(c)) for c in cases]
    made = [(c, p, g) for c, p, g in predicted if p is not None]
    has_gold = [(c, p, g) for c, p, g in predicted if g is not None]
    return {
        "precision": sum(p == g for _, p, g in made) / max(len(made), 1),
        "recall": sum(p == g for _, p, g in has_gold) / max(len(has_gold), 1),
        "set_where_unknown": [c["id"] for c, p, g in made if g is None],
        "future_given_start": [c["id"] for c, p, _ in made if c["category"] == "future"],
        "misses": [(c["id"], p, g) for c, p, g in predicted if p != g],
    }


def test_the_cases_are_well_formed():
    cases = DATA["world_time"]
    ids = [c["id"] for c in cases]
    assert len(ids) == len(set(ids))
    assert len(cases) >= 80
    tamil = [c for c in cases if c["lang"] in ("ta", "tanglish")]
    assert len(tamil) / len(cases) >= 0.25
    for lang in ("en", "ta", "tanglish"):
        mine = [c for c in cases if c["lang"] == lang]
        # Each language has starts, future phrases and negative (unknown) cases.
        assert any(c["expect"] for c in mine), lang
        assert any(c["category"] == "future" for c in mine), lang
        assert any(c["expect"] is None and c["category"] != "future" for c in mine), lang


def test_world_time_meets_the_adr_targets():
    s = _scores()
    assert s["set_where_unknown"] == [], s["misses"]
    assert s["future_given_start"] == [], s["misses"]
    assert s["precision"] >= TARGETS["precision"], s["misses"]
    assert s["recall"] >= TARGETS["recall"], s["misses"]


def test_tamil_and_tanglish_alone_meet_the_targets():
    tamil = [c for c in DATA["world_time"] if c["lang"] in ("ta", "tanglish")]
    made = [(c, _predict(c)) for c in tamil]
    assert [c["id"] for c, p in made if p is not None and c["expect"] is None] == []
    gold = [(c, p) for c, p in made if c["expect"] is not None]
    assert sum(p == _gold(c) for c, p in gold) / len(gold) >= TARGETS["recall"]

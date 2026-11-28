"""Unit tests for scripts/shadow_context_structure.py (ADR M8 ingestion §6.2).

Fake rows only: label-only output (no ref, fp, id or content string ever
reaches the summary or the text), the percentile maths, and the tenant
filter on every query.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from datetime import UTC, date, datetime

import pytest

from scripts import shadow_context_structure as scs

SINCE = datetime(2026, 11, 21, tzinfo=UTC)
REF = "memory:5b1c0d2e-aaaa-4bbb-8ccc-123456789abc"
FP = "deadbeefcafe0123"
SECRET = "Anu moved to Coimbatore"


# ── Percentiles ──────────────────────────────────────────────


def test_percentile_linear_interpolation():
    xs = [1, 2, 3, 4]
    assert scs.percentile(xs, 50) == pytest.approx(2.5)
    assert scs.percentile(xs, 95) == pytest.approx(3.85)
    assert scs.percentile(xs, 0) == 1
    assert scs.percentile(xs, 100) == 4


def test_percentile_one_value_and_empty():
    assert scs.percentile([7], 95) == 7
    assert scs.percentile([], 50) is None
    assert scs.percentile([None, float("nan")], 50) is None


def test_percentile_ignores_order():
    assert scs.percentile([10, 1, 5, 3, 8], 50) == 5


def test_spread_rounds_and_counts():
    assert scs.spread([1.0, 2.0, None, 4.0]) == {"n": 3, "p50": 2.0, "p95": 3.8, "max": 4.0}
    assert scs.spread([]) == {"n": 0, "p50": None, "p95": None, "max": None}


# ── Labels ───────────────────────────────────────────────────


def test_label_passes_only_known_vocabulary():
    assert scs.label("BECAUSE", "relation_type") == "BECAUSE"
    assert scs.label(REF, "relation_type") == "other"
    assert scs.label(FP, "decision_status") == "other"
    assert scs.label(None, "conflict_kind") == "unset"
    assert scs.label("supersession", "conflict_kind") == "supersession"
    assert scs.label(3, "change_kind") == "other"


# ── Summary from fake rows ───────────────────────────────────


def _turn(**kw):
    row = {
        "day": date(2026, 11, 25),
        "has_snapshot": True,
        "snapshot_ok": True,
        "snapshot_error": None,
        "abstain": False,
        "insufficient": False,
        "ms": 100.0,
        "timings_ms": {"embed": 10.0, "retrieve": 50.0, "total": 90.0},
        "items": 4,
        "memory_items": 3,
        "world_time_known": 1,
        "relations": 1,
        "conflicts": 1,
        "has_changes": True,
        "changes_ok": True,
        "changes_error": None,
        "baseline_found": True,
        "changes_insufficient": False,
        "read_failed": False,
        "changes_ms": 20.0,
        "changes": 2,
        "suppressed": {"duplicate": 1, "cosmetic": 2},
    }
    row.update(kw)
    return row


def _raw():
    """Fake rows, with a ref, an fp and content smuggled into every label slot."""
    return {
        "turns": [
            _turn(),
            _turn(
                day=date(2026, 11, 26),
                abstain=True,
                insufficient=True,
                ms=300.0,
                items=0,
                memory_items=0,
                world_time_known=0,
                relations=0,
                conflicts=0,
                timings_ms={"embed": 30.0, REF: 5.0, "total": 290.0},
                baseline_found=False,
                changes=0,
                suppressed={FP: 9},
            ),
            _turn(
                snapshot_ok=False,
                snapshot_error="TimeoutError",
                ms=3000.0,
                items=0,
                memory_items=0,
                world_time_known=0,
                relations=0,
                conflicts=0,
                timings_ms=None,
                has_changes=False,
                changes_ok=False,
            ),
            _turn(
                snapshot_ok=False,
                snapshot_error=SECRET,
                ms=5.0,
                items=0,
                memory_items=0,
                world_time_known=0,
                relations=0,
                conflicts=0,
                timings_ms=None,
                changes_ok=False,
                changes_error=REF,
            ),
        ],
        "item_kinds": [
            {"label": "memory", "n": 3, "world_time_known": 1},
            {"label": "decision", "n": 1, "world_time_known": 0},
            {"label": FP, "n": 2, "world_time_known": 0},
        ],
        "relation_types": [{"label": "BECAUSE", "n": 1}, {"label": REF, "n": 4}],
        "conflict_kinds": [{"label": "supersession", "n": 1}, {"label": SECRET, "n": 1}],
        "decision_items": [
            {"label": "candidate", "confirmed": False, "n": 2},
            {"label": "decided", "confirmed": True, "n": 1},
            {"label": FP, "confirmed": True, "n": 1},
        ],
        "abstention_reasons": [{"label": "contradictory_evidence", "n": 1}],
        "change_kinds": [
            {"label": "added", "acknowledged": False, "n": 2},
            {"label": "superseded", "acknowledged": True, "n": 1},
            {"label": REF, "acknowledged": False, "n": 1},
        ],
        "memories": [{"created": 10, "with_world_time": 4}],
        "world_time": [
            {"precision": "day", "source": "content", "n": 3},
            {"precision": SECRET, "source": FP, "n": 1},
        ],
        "supersession": [{"ended_all": 5, "ended_since": 2, "superseded_since": 3}],
        "typed_links": [{"label": "BECAUSE", "n": 2}, {"label": "LEADS_TO", "n": 1}],
        "decisions": [
            {"label": "candidate", "n": 7, "created_since": 2},
            {"label": SECRET, "n": 1, "created_since": 1},
        ],
        "contradictions": [
            {"label": "medium", "applied": False, "n": 4, "created_since": 1, "not_queued": 0},
            {"label": "low", "applied": False, "n": 5, "created_since": 5, "not_queued": 3},
            {"label": None, "applied": True, "n": 2, "created_since": 0, "not_queued": 0},
            {"label": REF, "applied": False, "n": 1, "created_since": 0, "not_queued": 0},
        ],
    }


def _summary():
    return scs.summarise(_raw(), tenant="t_unit", since=SINCE)


@pytest.mark.parametrize("leak", [REF, FP, SECRET, "5b1c0d2e", "Coimbatore"])
def test_no_ref_fp_or_content_reaches_the_output(leak):
    s = _summary()
    assert leak not in json.dumps(s, default=str)
    assert leak not in scs.render(s)


def test_snapshot_counts_and_rates():
    sn = _summary()["snapshot"]
    assert sn["turns_traced"] == 4
    assert sn["turns_with_snapshot"] == 2
    assert sn["errors"] == {"TimeoutError": 1, "other": 1}
    assert sn["abstain_rate"] == 0.5
    assert sn["insufficient_rate"] == 0.5
    assert sn["memory_items"] == 3
    assert sn["world_time_known"] == 1
    assert sn["world_time_known_share"] == pytest.approx(0.3333)
    assert sn["items_per_turn"] == {"n": 2, "p50": 2.0, "p95": 3.8, "max": 4.0}
    assert sn["items_by_kind"]["other"] == {"n": 2, "world_time_known": 0}
    assert sn["relation_types"] == {"BECAUSE": 1, "other": 4}
    assert sn["conflict_kinds"] == {"other": 1, "supersession": 1}
    assert sn["decision_items"] == {
        "candidate": {"n": 2, "confirmed": 0},
        "decided": {"n": 1, "confirmed": 1},
        "other": {"n": 1, "confirmed": 1},
    }
    # ms over every traced turn (errors too: a timeout is the slow tail).
    assert sn["ms"]["p50"] == 200.0
    assert sn["ms"]["max"] == 3000.0
    assert set(sn["timings_ms"]) == {"embed", "retrieve", "total", "other"}
    assert sn["timings_ms"]["embed"] == {"n": 2, "p50": 20.0, "p95": 29.0, "max": 30.0}


def test_changes_counts():
    ch = _summary()["changes"]
    assert ch["turns_traced"] == 3
    assert ch["turns_compared"] == 2
    assert ch["errors"] == {"other": 1}
    assert ch["baseline_found_rate"] == 0.5
    assert ch["read_failed"] == 0
    assert ch["kinds"]["superseded"] == {"n": 1, "acknowledged": 1}
    assert ch["kinds"]["other"] == {"n": 1, "acknowledged": 0}
    assert ch["suppressed"] == {"cosmetic": 2, "duplicate": 1, "other": 9}


def test_days_and_ingestion():
    s = _summary()
    assert list(s["days"]) == ["2026-11-25", "2026-11-26"]
    assert s["days"]["2026-11-25"]["snapshots"] == 1
    ing = s["ingestion"]
    assert ing["memories_created"] == 10
    assert ing["with_world_time"] == 4
    assert ing["world_time_precision"] == {"day": 3, "other": 1}
    assert ing["world_time_source"] == {"content": 3, "other": 1}
    assert ing["valid_until_by_supersession"] == 5
    assert ing["typed_links_by_type"] == {"BECAUSE": 2, "LEADS_TO": 1}
    assert ing["decisions_by_status"]["other"] == {"n": 1, "created_since": 1}
    assert ing["pending_contradictions_by_confidence"] == {
        "low": {"pending": 5, "applied": 0, "created_since": 5, "not_queued": 3},
        "medium": {"pending": 4, "applied": 0, "created_since": 1, "not_queued": 0},
        "other": {"pending": 1, "applied": 0, "created_since": 0, "not_queued": 0},
        "unset": {"pending": 2, "applied": 2, "created_since": 0, "not_queued": 0},
    }


def test_empty_rows_render():
    s = scs.summarise({}, tenant="t_unit", since=SINCE)
    assert s["snapshot"]["abstain_rate"] is None
    assert "none" in scs.render(s)


# ── Queries ──────────────────────────────────────────────────

_TABLE = re.compile(
    r"\b(?:FROM|JOIN)\s+(agent_tasks|memories|memory_links|life_graph\.decisions|approvals)\s+(\w+)"
)


def test_every_query_is_tenant_scoped():
    for name, sql in scs.QUERIES.items():
        tables = _TABLE.findall(sql)
        assert tables, name
        for _table, alias in tables:
            assert f"{alias}.tenant_id = :tenant" in sql, (name, alias)


def test_queries_select_no_ref_fp_or_content():
    for name, sql in scs.QUERIES.items():
        body = sql.split("FROM", 1)[0]
        for forbidden in ("'ref'", "'fp'", "'rec'", "content", "'refs'", "'approval'", "title"):
            if forbidden == "'ref'" and "split_part(i->>'ref'" in body:
                continue  # the ref's kind prefix only ("memory", "decision", ...)
            assert forbidden not in body, (name, forbidden)
        assert "SELECT *" not in sql
        for word in ("INSERT", "UPDATE", "DELETE", "ALTER", "DROP", "TRUNCATE"):
            assert not re.search(rf"\b{word}\b", sql), (name, word)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _Conn:
    def __init__(self):
        self.calls = []

    async def execute(self, stmt, params=None):
        self.calls.append((str(stmt), params or {}))
        return _Result([])


def test_collect_binds_the_tenant_on_every_query():
    conn = _Conn()
    raw = asyncio.run(scs.collect(conn, "t_unit", SINCE))
    assert set(raw) == set(scs.QUERIES)
    assert len(conn.calls) == len(scs.QUERIES)
    for sql, params in conn.calls:
        assert params["tenant"] == "t_unit", sql
        assert ":tenant" in sql


def test_read_only_sets_the_transaction_and_rolls_back():
    log = []

    class Conn(_Conn):
        async def rollback(self):
            log.append("rollback")

    conn = Conn()

    class Engine:
        def connect(self):
            class Ctx:
                async def __aenter__(self):
                    return conn

                async def __aexit__(self, *exc):
                    return False

            return Ctx()

    async def go():
        async with scs.read_only(Engine()) as c:
            await c.execute("SELECT 1")

    asyncio.run(go())
    assert conn.calls[0][0] == "SET TRANSACTION READ ONLY"
    assert log == ["rollback"]


def test_parse_since():
    now = datetime(2026, 11, 28, 12, tzinfo=UTC)
    assert scs.parse_since("7", now) == datetime(2026, 11, 21, 12, tzinfo=UTC)
    assert scs.parse_since("14d", now) == datetime(2026, 11, 14, 12, tzinfo=UTC)
    assert scs.parse_since("2026-11-20", now) == datetime(2026, 11, 20, tzinfo=UTC)
    with pytest.raises(argparse.ArgumentTypeError):
        scs.parse_since("last week", now)

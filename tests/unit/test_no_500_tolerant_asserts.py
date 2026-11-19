"""Ratchet: integration tests must not get more ``status_code in (..., 500)`` checks.

An assertion like ``assert r.status_code in (200, 500)`` passes when the
route crashes. Written for runs with no database, it outlived the reason:
CI has a real Postgres, ``skip_on_db_error`` already turns an unreachable
database into a skip, and in the meantime a crashing route reported green
(audit H5: 266 of these in 30 files on 2026-11-19).

The fix is ``assert_ok(response, expected)`` from tests/integration/conftest.py,
which never accepts a 5xx. Converting all of them at once is not safe without
running each one, so this test is a ratchet: every file may keep at most the
number it had when the file was last cleaned (``BASELINE``), and a file not
listed may have none. Lower a number when you convert a file; never raise one.

A deliberate 5xx in a tuple is fine when it is not 500 itself -- e.g. a
health probe that may answer 503 -- so only a literal 500 counts.
"""

from __future__ import annotations

import re
from pathlib import Path

INTEGRATION = Path(__file__).resolve().parents[1] / "integration"

# `status_code in (..., 500, ...)` -- also lists/sets; `not in` is excluded.
PATTERN = re.compile(r"(?<!not )\bin\s+[(\[{][^)\]}]*\b500\b")
STATUS = re.compile(r"status_code\s+in\s")

#: file (relative to tests/integration) -> allowed count. Only ever lower these.
BASELINE: dict[str, int] = {
    "test_advisor.py": 6,
    "test_agent_networks.py": 11,
    "test_approvals.py": 7,
    "test_autonomy.py": 10,
    "test_autonomy_approvals.py": 5,
    "test_autonomy_pipeline.py": 2,
    "test_contradiction_producer.py": 2,
    "test_conversation_distill.py": 2,
    "test_conversations_api.py": 10,
    "test_decay.py": 9,
    "test_dedup.py": 6,
    "test_evidence.py": 7,
    "test_kernel_notifications.py": 10,
    "test_kernel_projects.py": 8,
    "test_kernel_router.py": 12,
    "test_kernel_scheduler.py": 12,
    "test_memory_approval.py": 5,
    "test_merge_suggestions.py": 2,
    "test_preferences.py": 10,
    "test_push_api.py": 3,
    "test_research.py": 14,
    "test_search_filters.py": 10,
    "test_self_improving.py": 17,
    "test_transcript.py": 5,
    "test_watchers.py": 12,
}


def count_500_tolerant(text: str) -> int:
    """Lines asserting on a status code with 500 among the accepted values."""
    return sum(1 for line in text.splitlines() if STATUS.search(line) and PATTERN.search(line))


def test_pattern_matches_what_it_should() -> None:
    assert count_500_tolerant("assert r.status_code in (200, 500)") == 1
    assert count_500_tolerant("assert r.status_code in (200, 202, 500), (") == 1
    assert count_500_tolerant("assert resp.status_code in [404, 500]") == 1
    assert count_500_tolerant("assert r.status_code in (200, 503)") == 0
    assert count_500_tolerant("if r.status_code not in (200, 500):") == 0
    assert count_500_tolerant("assert_ok(r, 200)") == 0


def test_no_file_exceeds_its_500_tolerant_baseline() -> None:
    over = {}
    for path in sorted(INTEGRATION.rglob("*.py")):
        rel = path.relative_to(INTEGRATION).as_posix()
        found = count_500_tolerant(path.read_text(encoding="utf-8"))
        allowed = BASELINE.get(rel, 0)
        if found > allowed:
            over[rel] = (found, allowed)
    assert not over, (
        "integration tests that accept HTTP 500 as a pass, beyond the recorded "
        "baseline (file: (found, allowed)). Use assert_ok(response, expected) "
        f"from tests/integration/conftest.py instead: {over}"
    )


def test_baseline_names_only_existing_files() -> None:
    missing = [rel for rel in BASELINE if not (INTEGRATION / rel).exists()]
    assert not missing, f"drop these from BASELINE, they no longer exist: {missing}"
